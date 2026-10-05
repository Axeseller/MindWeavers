"""Shared loop for scripts/artifacts/<name>.py:
connect the Tello, subscribe to the Unicorn LSL stream, read until the artifact is detected, always shut down.

Cleaning lives in eeg.preprocess.ARTIFACT_CLEANING[name], decision parameters in eeg.detectors.ARTIFACT_PARAMS[name].
"""

from __future__ import annotations

import argparse
import csv
import time
from collections import deque
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import numpy as np

import _paths  # noqa: F401
from eeg.calibration import calibrated_params
from eeg.detectors import ThresholdDetector
from eeg.preprocess import ARTIFACT_CLEANING, SAMPLE_RATE, artifact_feature
from lsl.client import DEFAULT_STREAM_NAME, LslClient
from tello.controller import TelloController

STATUS_INTERVAL_S = 0.25
REPLAY_CHUNK = 10  # samples per pull while replaying a CSV (40 ms, close to the live stream)
CSV_COLUMNS = 17  # ch0..ch16 after the timestamp column

# Called with the controller on each detection. Return True to stop the script.
OnDetect = Callable[[TelloController], bool]


def parse_args(name: str, description: str) -> argparse.Namespace:
    params = calibrated_params()[name]
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--live", action="store_true", help="Connect to the real Tello (default is dry-run)")
    parser.add_argument("--stream", default=DEFAULT_STREAM_NAME, help="Unicorn raw LSL stream name")
    parser.add_argument("--threshold", type=float, default=params.threshold, help="Detection threshold")
    parser.add_argument("--replay", type=Path, help="Run on a recorded CSV instead of LSL (no hardware)")
    parser.add_argument("--quiet", action="store_true", help="Only print detections, not the feature every 0.25 s")
    return parser.parse_args()


def make_detector(name: str, threshold: float | None = None) -> ThresholdDetector:
    """Detector with the calibrated threshold (data/calibration/thresholds.json) unless one is given."""
    params = calibrated_params()[name]
    if threshold is not None:
        params = replace(params, threshold=threshold)
    return ThresholdDetector(params)


def load_csv(path: Path) -> np.ndarray:
    """Rows of the 17 Unicorn channels from a record_baseline.py CSV."""
    with path.open(newline="", encoding="latin-1") as handle:
        reader = csv.reader(handle)
        next(reader, None)
        rows = [row[1 : 1 + CSV_COLUMNS] for row in reader if len(row) > CSV_COLUMNS]
    return np.asarray(rows, dtype=np.float64).reshape(-1, CSV_COLUMNS)


class CsvReplayClient:
    """Stands in for LslClient: same pull_chunk/window interface, fed from a CSV, with simulated time."""

    def __init__(self, path: Path, buffer_seconds: float = 1.0) -> None:
        self._rows = load_csv(path)
        self._pos = 0
        self._buffer: deque[np.ndarray] = deque(maxlen=int(SAMPLE_RATE * buffer_seconds))
        self.path = path

    @property
    def finished(self) -> bool:
        return self._pos >= len(self._rows)

    def connect(self, stream_name: str = "") -> bool:
        print(f"Replaying {self.path.name} ({len(self._rows) / SAMPLE_RATE:.0f} s)")
        return len(self._rows) > 0

    def now(self) -> float:
        return self._pos / SAMPLE_RATE

    def pull_chunk(self, timeout: float = 0.0, max_samples: int = REPLAY_CHUNK) -> np.ndarray:
        chunk = self._rows[self._pos : self._pos + REPLAY_CHUNK]
        self._pos += len(chunk)
        self._buffer.extend(chunk)
        return chunk

    def window(self) -> np.ndarray:
        return np.vstack(self._buffer) if self._buffer else np.empty((0, CSV_COLUMNS))

    def close(self) -> None:
        self._buffer.clear()


def feature_series(name: str, rows: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(times, values) of one artifact's feature over a recording, updated like the live loop."""
    cleaning = ARTIFACT_CLEANING[name]
    times, values = [], []
    for end in range(SAMPLE_RATE, len(rows) + 1, REPLAY_CHUNK):
        times.append(end / SAMPLE_RATE)
        values.append(artifact_feature(rows[end - SAMPLE_RATE : end], cleaning))
    return np.asarray(times), np.asarray(values)


def detections(name: str, times: np.ndarray, values: np.ndarray, threshold: float | None = None) -> list[float]:
    detector = make_detector(name, threshold)
    return [float(t) for t, v in zip(times, values) if detector.update(float(v), float(t))]


def run(name: str, description: str, on_detect: OnDetect | None = None) -> None:
    args = parse_args(name, description)
    replay = args.replay is not None
    mode = "REPLAY" if replay else ("LIVE" if args.live else "DRY-RUN")
    print(f"[{name}] Mode: {mode}  threshold={args.threshold:.1f}")

    # 1. Connect to the drone (battery check happens inside connect)
    controller = TelloController(dry_run=not args.live or replay)
    if not controller.connect(with_video=False):
        return

    # 2. Subscribe to the headset (or the recording)
    client = CsvReplayClient(args.replay) if replay else LslClient()
    if not client.connect(stream_name=args.stream):
        controller.shutdown()
        raise SystemExit(1)

    cleaning = ARTIFACT_CLEANING[name]
    detector = make_detector(name, args.threshold)
    clock = client.now if replay else time.monotonic
    print(f"\nDo the '{name}' artifact. Ctrl+C exits.\n")

    # 3. Read live data and print every detection
    count = 0
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

            value = artifact_feature(window, cleaning)
            now = clock()
            detected = detector.update(value, now)

            if not args.quiet and now >= next_status:
                state = "ACTIVE" if detector.active else "rest"
                print(f"{name}={value:7.2f}  {state}")
                next_status = now + STATUS_INTERVAL_S

            if detected:
                count += 1
                stamp = f"t={now:5.1f}s  " if replay else ""
                print(f">>> DETECTED: {name}  #{count}  {stamp}peak={detector.peak:.2f}")
                if on_detect is not None and on_detect(controller):
                    break
    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        # 4. Always land and release resources
        client.close()
        controller.shutdown()
        print(f"[{name}] detections: {count}")
