from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np

import _paths  # noqa: F401
from eeg.detectors import JAW_TAKEOFF_THRESHOLD, ArtifactDetector, jaw_takeoff_config
from eeg.preprocess import EEG_CHANNEL_COUNT, SAMPLE_RATE, extract_features, preprocess_window
from mapping.commands import Event

WINDOW_SAMPLES = SAMPLE_RATE
STEP_SAMPLES = SAMPLE_RATE // 10
PERCENTILES = (5, 25, 50, 75, 95, 99, 100)
CANDIDATE_THRESHOLDS = (25.0, 30.0, 35.0, 40.0, 45.0, 50.0)
REST_MARGIN = 1.2


def load_eeg(path: Path) -> np.ndarray:
    """Read the first eight EEG columns by position so old and new CSV headers both work."""
    with path.open(newline="") as handle:
        reader = csv.reader(handle)
        next(reader)
        rows = [row[1 : 1 + EEG_CHANNEL_COUNT] for row in reader if len(row) > EEG_CHANNEL_COUNT]
    if not rows:
        raise SystemExit(f"{path} has no samples.")
    return np.asarray(rows, dtype=np.float64)


def jaw_rms_series(eeg: np.ndarray) -> np.ndarray:
    values = []
    for start in range(0, len(eeg) - WINDOW_SAMPLES + 1, STEP_SAMPLES):
        window = preprocess_window(eeg[start : start + WINDOW_SAMPLES])
        jaw_rms, _blink = extract_features(window)
        values.append(jaw_rms)
    return np.asarray(values)


def crossing_durations(values: np.ndarray, threshold: float) -> list[float]:
    edges = np.diff(np.r_[False, values >= threshold, False].astype(int))
    starts = np.flatnonzero(edges == 1)
    ends = np.flatnonzero(edges == -1)
    step_s = STEP_SAMPLES / SAMPLE_RATE
    return [round(float(n) * step_s, 1) for n in ends - starts]


def replay_events(values: np.ndarray, threshold: float) -> list[str]:
    detector = ArtifactDetector(jaw_takeoff_config(threshold))
    step_s = STEP_SAMPLES / SAMPLE_RATE
    events: list[str] = []
    for i, jaw_rms in enumerate(values):
        events.extend(detector.update(float(jaw_rms), 0.0, i * step_s))
    return events


def summarize(label: str, values: np.ndarray) -> None:
    stats = np.percentile(values, PERCENTILES)
    joined = "  ".join(f"p{p}={v:.1f}" for p, v in zip(PERCENTILES, stats))
    print(f"{label:<5} windows={len(values):4d}  {joined}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare rest vs jaw-clench recordings and suggest a threshold")
    parser.add_argument("--rest", type=Path, required=True)
    parser.add_argument("--jaw", type=Path, required=True)
    parser.add_argument("--threshold", type=float, default=JAW_TAKEOFF_THRESHOLD, help="Threshold to replay")
    args = parser.parse_args()

    rest = jaw_rms_series(load_eeg(args.rest))
    jaw = jaw_rms_series(load_eeg(args.jaw))
    print("Jaw RMS feature (15-40 Hz, 1 s window, 8 EEG channels)")
    summarize("rest", rest)
    summarize("jaw", jaw)

    print("\nThreshold  rest-crossings  jaw-crossings (durations in s)")
    for threshold in CANDIDATE_THRESHOLDS:
        rest_runs = crossing_durations(rest, threshold)
        jaw_runs = crossing_durations(jaw, threshold)
        print(f"{threshold:9.1f}  {len(rest_runs):14d}  {len(jaw_runs):3d} {jaw_runs}")

    print(f"\nDetector replay at threshold {args.threshold:.1f} (takeoff triggers = {Event.JAW_SHORT.value})")
    for label, values in (("rest", rest), ("jaw", jaw)):
        events = replay_events(values, args.threshold)
        short = sum(event == Event.JAW_SHORT for event in events)
        print(f"{label:<5} {Event.JAW_SHORT.value}={short}  other={len(events) - short}")

    floor = float(rest.max()) * REST_MARGIN
    ceiling = float(np.percentile(jaw, 95))
    if floor >= ceiling:
        print(f"\nNo clean separation: rest max x{REST_MARGIN} = {floor:.1f} >= jaw p95 = {ceiling:.1f}.")
        return
    recommended = round((floor + ceiling) / 2)
    print(f"\nRecommended jaw threshold: {recommended} (rest max x{REST_MARGIN}={floor:.1f}, jaw p95={ceiling:.1f})")


if __name__ == "__main__":
    main()
