"""Camera mode: close your eyes (held 1.5 s) to turn the Tello camera on, close them again to turn it off,
and blink to take a photo while it is on.

Runs the cerrar_ojos and blink detectors together, because closing or opening the eyes also looks like a blink:
- a blink waits BLINK_CONFIRM_S before it counts; if the eyes stay closed meanwhile, it was the start of a close.
- blinks right after the eyes open (AFTER_EYES_OPEN_S) are ignored.

    python scripts/artifacts/camera.py                  # headset LSL, Tello dry-run
    python scripts/artifacts/camera.py --live           # headset LSL, real Tello
    python scripts/artifacts/camera.py --replay <csv>   # recorded CSV, no hardware
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import _paths  # noqa: F401
from _live import CsvReplayClient, make_detector
from camera_actions import take_photo, toggle_camera
from eeg.preprocess import ARTIFACT_CLEANING, SAMPLE_RATE, artifact_feature
from lsl.client import DEFAULT_STREAM_NAME, LslClient
from tello.controller import TelloController

BLINK_CONFIRM_S = 0.6
AFTER_EYES_OPEN_S = 1.0
STATUS_INTERVAL_S = 0.25


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Eyes closed toggles the Tello camera, blink takes a photo")
    parser.add_argument("--live", action="store_true", help="Connect to the real Tello (default is dry-run)")
    parser.add_argument("--stream", default=DEFAULT_STREAM_NAME, help="Unicorn raw LSL stream name")
    parser.add_argument("--replay", type=Path, help="Run on a recorded CSV instead of LSL (no hardware)")
    parser.add_argument("--camera-on", action="store_true", help="Start with the camera already on")
    parser.add_argument("--quiet", action="store_true", help="Only print events, not the features every 0.25 s")
    return parser.parse_args()


class CameraMode:
    """Decides, tick by tick, when to toggle the camera and when a blink is a photo."""

    def __init__(self) -> None:
        self.eyes = make_detector("cerrar_ojos")
        self.blink = make_detector("blink")
        self._blink_at: float | None = None
        self._quiet_until = 0.0

    def update(self, eyes_value: float, blink_value: float, now: float) -> list[str]:
        """Returns the actions due now: "toggle_camera" and/or "photo"."""
        actions = []
        if self.eyes.update(eyes_value, now):
            actions.append("toggle_camera")
        blinked = self.blink.update(blink_value, now)
        if self.eyes.active:
            self._blink_at = None
            self._quiet_until = now + AFTER_EYES_OPEN_S
        elif blinked and now >= self._quiet_until:
            self._blink_at = now
        if self._blink_at is not None and now - self._blink_at >= BLINK_CONFIRM_S:
            self._blink_at = None
            actions.append("photo")
        return actions


def main() -> None:
    args = parse_args()
    replay = args.replay is not None
    print(f"[camera] Mode: {'REPLAY' if replay else ('LIVE' if args.live else 'DRY-RUN')}")

    # 1. Connect to the drone
    controller = TelloController(dry_run=not args.live or replay)
    if not controller.connect(with_video=args.camera_on):
        return

    # 2. Subscribe to the headset (or the recording)
    client = CsvReplayClient(args.replay) if replay else LslClient()
    if not client.connect(stream_name=args.stream):
        controller.shutdown()
        raise SystemExit(1)

    mode = CameraMode()
    clock = client.now if replay else time.monotonic
    print("\nClose your eyes 1.5 s: camera on/off. Blink: photo. Ctrl+C exits.\n")

    # 3. Read live data and act on each event
    photos = toggles = 0
    next_status = 0.0
    try:
        while True:
            chunk = client.pull_chunk(timeout=0.05)
            if chunk.size == 0:
                if replay and client.finished:
                    break
                continue
            window = client.window()
            if len(window) < SAMPLE_RATE:
                continue

            eyes_value = artifact_feature(window, ARTIFACT_CLEANING["cerrar_ojos"])
            blink_value = artifact_feature(window, ARTIFACT_CLEANING["blink"])
            now = clock()
            actions = mode.update(eyes_value, blink_value, now)

            if not args.quiet and now >= next_status:
                eyes = "CLOSED" if mode.eyes.active else "open"
                cam = "ON" if controller.camera_on else "off"
                print(f"eyes={eyes_value:5.2f} {eyes:6s}  blink={blink_value:6.1f}  camera={cam}")
                next_status = now + STATUS_INTERVAL_S

            stamp = f"t={now:5.1f}s  " if replay else ""
            for action in actions:
                if action == "toggle_camera":
                    toggles += 1
                    print(f">>> DETECTED: cerrar_ojos  {stamp}-> camera {'off' if controller.camera_on else 'on'}")
                    toggle_camera(controller)
                else:
                    photos += 1
                    print(f">>> DETECTED: blink  {stamp}-> photo")
                    take_photo(controller)
            if controller.camera_on and not replay:
                controller.record_frame()
    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        # 4. Always land and release resources
        client.close()
        controller.shutdown()
        print(f"[camera] camera toggles: {toggles}  photos: {photos}")


if __name__ == "__main__":
    main()
