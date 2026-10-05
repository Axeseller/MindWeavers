"""All seven inputs on one stream, one decision at a time (eeg.arbiter), mapped to the Tello:

    jaw          -> takeoff when grounded, land when flying
    cerrar_ojos  -> camera on / off
    blink        -> photo (while the camera is on)
    happy        -> forward pulse
    puno         -> back pulse
    cuello       -> right pulse
    angry        -> left pulse

    python scripts/artifacts/fly.py                    # headset LSL, Tello dry-run (prints what it would do)
    python scripts/artifacts/fly.py --live             # headset LSL, real Tello
    python scripts/artifacts/fly.py --replay <csv>     # recorded CSV, no hardware
    python scripts/artifacts/fly.py --inputs jaw,cuello,blink   # only some inputs
    python scripts/artifacts/fly.py --threshold cuello=20       # try another threshold
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import _paths  # noqa: F401
from _live import CsvReplayClient
from camera_actions import take_photo, toggle_camera
from eeg.arbiter import PRIORITY, InputArbiter
from eeg.calibration import DEFAULT_PATH as CALIBRATION, calibrated_params, load as load_calibration
from eeg.preprocess import ARTIFACT_CLEANING, GAUGE_CLEANING, SAMPLE_RATE, artifact_feature
from lsl.client import DEFAULT_STREAM_NAME, LslClient
from tello.controller import TelloController
from tello.skills import SkillRunner

PULSES = {"happy": "forward", "puno": "back", "cuello": "right", "angry": "left"}
PULSE_S = 1.0
STATUS_INTERVAL_S = 0.25
LOOP_SLEEP_S = 0.005
SHUTDOWN_WAIT_S = 30.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Unicorn artifacts -> Tello, one input at a time")
    parser.add_argument("--live", action="store_true", help="Connect to the real Tello (default is dry-run)")
    parser.add_argument("--stream", default=DEFAULT_STREAM_NAME, help="Unicorn raw LSL stream name")
    parser.add_argument("--replay", type=Path, help="Run on a recorded CSV instead of LSL (no hardware)")
    parser.add_argument("--inputs", default=",".join(PRIORITY), help="Comma-separated inputs to enable")
    parser.add_argument("--threshold", action="append", default=[], metavar="INPUT=VALUE", help="Override a threshold")
    parser.add_argument("--camera-on", action="store_true", help="Start with the camera already on")
    parser.add_argument("--quiet", action="store_true", help="Only print inputs, not the features every 0.25 s")
    parser.add_argument("--why", action="store_true", help="Also print the firings the arbiter dropped, and why")
    parser.add_argument("--no-calibration", action="store_true", help="Ignore data/calibration/thresholds.json")
    return parser.parse_args()


def build_arbiter(args: argparse.Namespace) -> InputArbiter:
    names = tuple(name.strip() for name in args.inputs.split(",") if name.strip())
    if args.no_calibration or not load_calibration():
        print("[fly] thresholds: tested defaults (run calibrate.py to fit them to you)")
        arbiter = InputArbiter(names)
    else:
        print(f"[fly] thresholds: calibrated, from {CALIBRATION}")
        arbiter = InputArbiter(names, params=calibrated_params())
    for item in args.threshold:
        name, _, value = item.partition("=")
        arbiter.with_threshold(name, float(value))
    return arbiter


def apply(name: str, runner: SkillRunner) -> str:
    """Run the drone action for a confirmed input; returns what was done, for the log."""
    controller = runner.controller
    if name == "jaw":
        skill = "land" if controller.is_flying else "takeoff"
        return skill if runner.request(skill) else f"{skill} rejected (busy)"
    if name == "cerrar_ojos":
        toggle_camera(controller)
        return "camera on" if controller.camera_on else "camera off"
    if name == "blink":
        take_photo(controller)
        return "photo" if controller.camera_on else "photo skipped (camera off)"
    skill = PULSES[name]
    if not controller.is_flying:
        return f"{skill} skipped (not flying)"
    return f"{skill} {PULSE_S:.0f} s" if runner.request(skill, lease_s=PULSE_S) else f"{skill} rejected (busy)"


def main() -> None:
    args = parse_args()
    replay = args.replay is not None
    arbiter = build_arbiter(args)
    print(f"[fly] Mode: {'REPLAY' if replay else ('LIVE' if args.live else 'DRY-RUN')}  inputs: {', '.join(arbiter.inputs)}")

    # 1. Connect to the drone (battery check happens inside connect)
    controller = TelloController(dry_run=not args.live or replay)
    if not controller.connect(with_video=args.camera_on):
        return
    runner = SkillRunner(controller, dry_run_process_s=0.0 if replay else 1.5)

    # 2. Subscribe to the headset (or the recording)
    client = CsvReplayClient(args.replay) if replay else LslClient()
    if not client.connect(stream_name=args.stream):
        controller.shutdown()
        raise SystemExit(1)

    cleaning = {name: ARTIFACT_CLEANING[name] for name in arbiter.inputs}
    clock = client.now if replay else time.monotonic
    print("\nJaw: takeoff/land. Eyes closed: camera. Blink: photo. Smile: forward. Fist: back. Neck: right. Frown: left.")
    print("Ctrl+C lands and exits.\n")

    # 3. Read the stream, let the arbiter pick one input at a time, act on it
    counts: dict[str, int] = {}
    next_status = 0.0
    try:
        while True:
            chunk = client.pull_chunk(timeout=0.05)
            if chunk.size == 0:
                if replay and client.finished:
                    break
                runner.tick()
                continue
            window = client.window()
            if len(window) < SAMPLE_RATE:
                continue

            values = {name: artifact_feature(window, spec) for name, spec in cleaning.items()}
            now = clock()
            gauges = {name: artifact_feature(window, spec) for name, spec in GAUGE_CLEANING.items()}
            confirmed = arbiter.update(values, now, gauges)
            stamp = f"t={now:5.1f}s  " if replay else ""

            if args.why:
                for name, reason in arbiter.dropped:
                    print(f"    dropped {name}: {reason}")
            if confirmed:
                counts[confirmed] = counts.get(confirmed, 0) + 1
                print(f">>> INPUT: {confirmed:12s} {stamp}-> {apply(confirmed, runner)}")
            elif not args.quiet and now >= next_status:
                active = [name for name in arbiter.inputs if arbiter.active(name)]
                line = "  ".join(f"{name}={values[name]:6.1f}" for name in arbiter.inputs)
                print(f"{line}  {'ACTIVE: ' + ','.join(active) if active else ''}")
                next_status = now + STATUS_INTERVAL_S

            runner.tick()
            if controller.camera_on and not replay:
                controller.record_frame()
            if not replay:
                time.sleep(LOOP_SLEEP_S)
    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        # 4. Always land and release resources
        client.close()
        runner.wait_idle(SHUTDOWN_WAIT_S)
        controller.shutdown()
        print("[fly] inputs: " + (", ".join(f"{k}={v}" for k, v in counts.items()) or "none"))


if __name__ == "__main__":
    main()
