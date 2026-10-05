"""Simple flight with three inputs, ready for the real Tello:

    jaw (1st time)  -> takeoff
    cuello          -> forward 1 s   (turn the head to the RIGHT, then back)
    blink           -> back 1 s
    jaw (2nd time)  -> land

Uses the same detectors, arbiter and calibration as fly.py (data/calibration/thresholds.json when it exists).

    python scripts/artifacts/vuelo.py               # REAL Tello: connect to its Wi-Fi first
    python scripts/artifacts/vuelo.py --dry-run     # no drone, prints what it would do
    python scripts/artifacts/vuelo.py --replay <csv> --dry-run   # a recording, no hardware

Ctrl+C lands and exits at any time.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import _paths  # noqa: F401
from _live import CsvReplayClient
from eeg.arbiter import InputArbiter
from eeg.calibration import DEFAULT_PATH as CALIBRATION, calibrated_params, load as load_calibration
from eeg.preprocess import ARTIFACT_CLEANING, GAUGE_CLEANING, SAMPLE_RATE, artifact_feature
from lsl.client import DEFAULT_STREAM_NAME, LslClient
from tello.controller import TelloController
from tello.skills import SkillRunner

INPUTS = ("jaw", "cuello", "blink")
PULSES = {"cuello": "forward", "blink": "back"}
PULSE_S = 1.0
STATUS_INTERVAL_S = 0.5
LOOP_SLEEP_S = 0.005
SHUTDOWN_WAIT_S = 30.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Jaw: takeoff/land. Neck: forward. Blink: back.")
    parser.add_argument("--dry-run", action="store_true", help="Do not connect to the Tello; print instead")
    parser.add_argument("--stream", default=DEFAULT_STREAM_NAME, help="Unicorn raw LSL stream name")
    parser.add_argument("--replay", type=Path, help="Run on a recorded CSV instead of LSL (use with --dry-run)")
    parser.add_argument("--threshold", action="append", default=[], metavar="INPUT=VALUE", help="Override a threshold")
    parser.add_argument("--why", action="store_true", help="Also print the firings the arbiter dropped, and why")
    return parser.parse_args()


def build_arbiter(args: argparse.Namespace) -> InputArbiter:
    if load_calibration():
        print(f"Thresholds: calibrated ({CALIBRATION})")
        arbiter = InputArbiter(INPUTS, params=calibrated_params())
    else:
        print("Thresholds: tested defaults (run calibrate.py --inputs jaw,cuello,blink to fit them to you)")
        arbiter = InputArbiter(INPUTS)
    for item in args.threshold:
        name, _, value = item.partition("=")
        arbiter.with_threshold(name, float(value))
    return arbiter


def apply(name: str, runner: SkillRunner) -> str:
    flying = runner.controller.is_flying
    if name == "jaw":
        skill = "land" if flying else "takeoff"
        return skill.upper() if runner.request(skill) else f"{skill} rejected (busy)"
    skill = PULSES[name]
    if not flying:
        return f"{skill} ignored (take off first with the jaw)"
    return f"{skill.upper()} {PULSE_S:.0f} s" if runner.request(skill, lease_s=PULSE_S) else f"{skill} rejected (busy)"


def main() -> None:
    args = parse_args()
    replay = args.replay is not None
    dry_run = args.dry_run or replay
    print(f"Mode: {'DRY-RUN (no drone)' if dry_run else 'LIVE - real Tello'}")
    arbiter = build_arbiter(args)

    # 1. Connect to the drone (battery check happens inside connect)
    controller = TelloController(dry_run=dry_run)
    if not controller.connect(with_video=False):
        return
    runner = SkillRunner(controller, dry_run_process_s=0.0 if replay else 1.5)

    # 2. Subscribe to the headset (or the recording)
    client = CsvReplayClient(args.replay) if replay else LslClient()
    if not client.connect(stream_name=args.stream):
        controller.shutdown()
        raise SystemExit(1)

    clock = client.now if replay else time.monotonic
    print("\n  JAW clench      -> takeoff (1st) / land (2nd)")
    print("  Head RIGHT     -> forward")
    print("  BLINK          -> back")
    print("  Ctrl+C         -> land and exit\n")

    # 3. One input at a time from the arbiter, straight to the drone
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

            values = {name: artifact_feature(window, ARTIFACT_CLEANING[name]) for name in INPUTS}
            gauges = {name: artifact_feature(window, spec) for name, spec in GAUGE_CLEANING.items()}
            now = clock()
            confirmed = arbiter.update(values, now, gauges)
            stamp = f"t={now:5.1f}s  " if replay else ""

            if args.why:
                for name, reason in arbiter.dropped:
                    print(f"    dropped {name}: {reason}")
            if confirmed:
                print(f">>> {confirmed:7s} {stamp}-> {apply(confirmed, runner)}")
            elif now >= next_status:
                state = "FLYING" if controller.is_flying else "grounded"
                line = "  ".join(f"{name}={values[name]:6.1f}" for name in INPUTS)
                print(f"{line}   {state}")
                next_status = now + STATUS_INTERVAL_S

            runner.tick()
            if not replay:
                time.sleep(LOOP_SLEEP_S)
    except KeyboardInterrupt:
        print("\nInterrupted: landing.")
    finally:
        # 4. Always land and release resources
        client.close()
        runner.wait_idle(SHUTDOWN_WAIT_S)
        controller.shutdown()


if __name__ == "__main__":
    main()
