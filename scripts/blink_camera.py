from __future__ import annotations

import argparse
import time
from pathlib import Path

import _paths  # noqa: F401
from eeg.detectors import (
    BLINK_PHOTO_THRESHOLD,
    EYES_CLOSED_THRESHOLD,
    ArtifactDetector,
    camera_blink_config,
)
from eeg.preprocess import SAMPLE_RATE, extract_eye_features, preprocess_window
from lsl.client import DEFAULT_STREAM_NAME, LslClient
from mapping.commands import Event
from tello.controller import TelloController

# Set these before running. At least one should be True to capture media.
CAMERA_START_ON_CONNECT = True
CAMERA_START_ON_CAPTURE = False

STATUS_INTERVAL_S = 0.25
MEDIA_DIR = Path(__file__).resolve().parents[1] / "data" / "recordings"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Tello photo/video from blink and eyes-closed (Unicorn LSL)")
    parser.add_argument("--live", action="store_true", help="Connect to the real Tello (default is dry-run)")
    parser.add_argument("--stream", default=DEFAULT_STREAM_NAME, help="Unicorn raw LSL stream name")
    parser.add_argument("--blink-threshold", type=float, default=BLINK_PHOTO_THRESHOLD)
    parser.add_argument("--eyes-closed-threshold", type=float, default=EYES_CLOSED_THRESHOLD)
    return parser.parse_args()


def camera_ready(controller: TelloController) -> bool:
    if controller.camera_on:
        return True
    if not CAMERA_START_ON_CAPTURE:
        print("Camera is off. Set CAMERA_START_ON_CONNECT or CAMERA_START_ON_CAPTURE.")
        return False
    return controller.start_camera()


def take_photo(controller: TelloController) -> None:
    if camera_ready(controller):
        controller.take_photo(MEDIA_DIR)


def start_video(controller: TelloController) -> None:
    if camera_ready(controller):
        controller.start_recording(MEDIA_DIR)


def apply_eye_event(controller: TelloController, event: str) -> None:
    if event == Event.BLINK:
        take_photo(controller)
    elif event == Event.EYES_CLOSED:
        start_video(controller)
    elif event == Event.EYES_OPENED:
        controller.stop_recording()


def read_eye_features(client: LslClient) -> tuple[float, float] | None:
    chunk = client.pull_chunk(timeout=0.05)
    if chunk.size == 0:
        return None
    window = client.window()
    if len(window) < SAMPLE_RATE:
        return None
    return extract_eye_features(preprocess_window(window))


def print_status(blink_peak: float, eyes_amp: float, detector: ArtifactDetector, recording: bool) -> None:
    eyes = "CLOSED" if detector.eyes_closed else "open"
    rec = "REC" if recording else "idle"
    print(f"blink_peak={blink_peak:6.1f}  eyes_amp={eyes_amp:5.1f}  {eyes}  cam={rec}")


def main() -> None:
    args = parse_args()
    mode = "LIVE" if args.live else "DRY-RUN"
    print(f"Mode: {mode}  blink={args.blink_threshold:.1f}  eyes_closed={args.eyes_closed_threshold:.1f}")
    print(f"Camera: start_on_connect={CAMERA_START_ON_CONNECT}  start_on_capture={CAMERA_START_ON_CAPTURE}")

    controller = TelloController(dry_run=not args.live)
    if not controller.connect(with_video=CAMERA_START_ON_CONNECT):
        return

    client = LslClient()
    if not client.connect(stream_name=args.stream):
        controller.shutdown()
        raise SystemExit(1)

    detector = ArtifactDetector(camera_blink_config(args.blink_threshold, args.eyes_closed_threshold))
    print("\nBlink once to take a photo. Keep your eyes closed for ~2 s to start video; open them to stop.")
    print("Ctrl+C saves any clip and exits.\n")
    run_loop(client, controller, detector)


def run_loop(client: LslClient, controller: TelloController, detector: ArtifactDetector) -> None:
    next_status = 0.0
    try:
        while True:
            features = read_eye_features(client)
            if features is None:
                pump_camera(controller)
                continue
            blink_peak, eyes_amp = features
            now = time.monotonic()
            events = detector.update(0.0, blink_peak, now, eyes_amp)
            if now >= next_status:
                print_status(blink_peak, eyes_amp, detector, controller.is_recording)
                next_status = now + STATUS_INTERVAL_S
            for event in events:
                print(f"EEG event: {event}  blink_peak={blink_peak:.1f}  eyes_amp={eyes_amp:.1f}")
                apply_eye_event(controller, event)
            pump_camera(controller)
    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        client.close()
        controller.shutdown()


def pump_camera(controller: TelloController) -> None:
    if not controller.camera_on:
        return
    controller.record_frame()
    controller.show_video()


if __name__ == "__main__":
    main()
