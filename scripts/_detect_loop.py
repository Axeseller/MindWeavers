from __future__ import annotations

import argparse
import time

import _paths  # noqa: F401
from eeg.detectors import ArtifactSpec, HoldDetector, artifact_spec
from eeg.preprocess import SAMPLE_RATE, extract_named, preprocess_window
from lsl.client import DEFAULT_STREAM_NAME, LslClient

STATUS_INTERVAL_S = 0.25


def parse_detect_args(spec: ArtifactSpec) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=f"Detect {spec.name} from Unicorn LSL (print only)")
    parser.add_argument("--stream", default=DEFAULT_STREAM_NAME)
    parser.add_argument("--threshold", type=float, default=spec.threshold)
    return parser.parse_args()


def read_feature(client: LslClient, feature: str) -> float | None:
    chunk = client.pull_chunk(timeout=0.05)
    if chunk.size == 0:
        return None
    window = client.window()
    if len(window) < SAMPLE_RATE:
        return None
    return extract_named(preprocess_window(window), feature)


def run_detect(name: str) -> None:
    spec = artifact_spec(name)
    args = parse_detect_args(spec)
    spec = artifact_spec(name, args.threshold)
    print(f"Detecting {spec.event}  feature={spec.feature}  threshold={spec.threshold:.2f}")
    print(spec.prompt)
    print("Ctrl+C exits. No drone commands are sent.\n")

    client = LslClient()
    if not client.connect(stream_name=args.stream):
        raise SystemExit(1)
    detector = HoldDetector(spec)
    next_status = 0.0
    try:
        while True:
            value = read_feature(client, spec.feature)
            if value is None:
                continue
            now = time.monotonic()
            event = detector.update(value, now)
            if now >= next_status:
                state = "ACTIVE" if detector.active else "rest"
                print(f"{spec.feature}={value:7.2f}  {state}")
                next_status = now + STATUS_INTERVAL_S
            if event:
                print(f"DETECTED {event}  {spec.feature}={value:.2f}")
    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        client.close()
