from __future__ import annotations

import argparse
import time

import _paths  # noqa: F401
from eeg.detectors import JAW_TAKEOFF_THRESHOLD, ArtifactDetector, jaw_takeoff_config
from eeg.preprocess import SAMPLE_RATE, extract_features, preprocess_window
from lsl.client import DEFAULT_STREAM_NAME, LslClient
from mapping.commands import Event
from tello.controller import TelloController

STATUS_INTERVAL_S = 0.25
HOVER_SECONDS = 8.0
HOVER_TICK_S = 0.1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Take off the Tello with one short jaw clench (Unicorn LSL)")
    parser.add_argument("--live", action="store_true", help="Connect to the real Tello (default is dry-run)")
    parser.add_argument("--stream", default=DEFAULT_STREAM_NAME, help="Unicorn raw LSL stream name")
    parser.add_argument("--threshold", type=float, default=JAW_TAKEOFF_THRESHOLD, help="Jaw RMS enter threshold")
    parser.add_argument("--hover-seconds", type=float, default=HOVER_SECONDS, help="Hover time before auto-landing")
    return parser.parse_args()


def fly_once(controller: TelloController, hover_seconds: float) -> None:
    """Take off, hover in place, then land."""
    controller.takeoff()
    print(f"Hovering for {hover_seconds:.0f} s...")
    end = time.monotonic() + hover_seconds
    while time.monotonic() < end:
        controller.hover()
        time.sleep(HOVER_TICK_S)
    controller.land()


def main() -> None:
    args = parse_args()
    mode = "LIVE" if args.live else "DRY-RUN"
    print(f"Mode: {mode}  threshold={args.threshold:.1f}")

    # 1. Connect to the drone (battery check happens inside connect)
    controller = TelloController(dry_run=not args.live)
    if not controller.connect(with_video=False):
        return

    # 2. Subscribe to the headset
    client = LslClient()
    if not client.connect(stream_name=args.stream):
        controller.shutdown()
        raise SystemExit(1)

    detector = ArtifactDetector(jaw_takeoff_config(args.threshold))
    print(f"\nClench your jaw for ~0.5-1 s to take off; it lands after {args.hover_seconds:.0f} s.")
    print("Ctrl+C lands and exits at any time.\n")

    # 3. Read live EEG until a clench is detected, then fly once
    next_status = 0.0
    try:
        while True:
            chunk = client.pull_chunk(timeout=0.05)
            if chunk.size == 0:
                continue
            window = client.window()
            if len(window) < SAMPLE_RATE:
                continue

            jaw_rms, _blink = extract_features(preprocess_window(window))
            now = time.monotonic()
            events = detector.update(jaw_rms, 0.0, now)

            if now >= next_status:
                state = "CLENCH" if detector.jaw_active else "rest"
                print(f"jaw_rms={jaw_rms:6.1f}  {state}")
                next_status = now + STATUS_INTERVAL_S

            for event in events:
                print(f"EEG event: {event}  jaw_rms={jaw_rms:.1f}")
            if Event.JAW_SHORT in events:
                fly_once(controller, args.hover_seconds)
                print("Mission complete.")
                break
    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        # 4. Always land and release resources
        client.close()
        controller.shutdown()


if __name__ == "__main__":
    main()
