"""Guided calibration, ~5 minutes. Do it once per person and session, before src/app.py.

It asks for 20 s of rest and then each input a few times, saving the raw stream per step. Then, for each input,
it picks the threshold that best separates your gesture from rest and from your other gestures, shows how the flight
would read the whole session, and saves the thresholds to data/calibration/thresholds.json. src/app.py and the
single-input scripts load that file automatically.

    python scripts/artifacts/calibrate.py                         # record with the headset, then calibrate
    python scripts/artifacts/calibrate.py --reps 8                # more repetitions per input
    python scripts/artifacts/calibrate.py --analyze <session dir> # recalibrate from a saved session
    python scripts/artifacts/calibrate.py --recordings <csv dir>  # calibrate from the 2026-10-04 recordings
"""

from __future__ import annotations

import argparse
import csv
import time
from datetime import datetime
from pathlib import Path

import numpy as np

import _paths  # noqa: F401
from _live import CSV_COLUMNS, load_csv
from check_all import OWN, RECORDINGS, find, segment
from eeg import calibration
from eeg.arbiter import PRIORITY
from eeg.preprocess import SAMPLE_RATE
from lsl.client import DEFAULT_STREAM_NAME

SESSIONS_DIR = Path(__file__).resolve().parents[2] / "data" / "calibration"
REST_S = 20.0
SETTLE_S = 5.0
# Input -> (instruction, seconds per repetition, seconds the gesture is held)
STEPS: dict[str, tuple[str, float, float]] = {
    "jaw": ("Clench your jaw firmly for ~1 s", 4.0, 1.0),
    "cerrar_ojos": ("Close your eyes and keep them closed until told to open", 6.0, 3.0),
    "blink": ("Blink once, firmly", 3.0, 0.3),
    "puno": ("Close a fist hard, stay still otherwise", 4.0, 1.0),
    "cuello": ("Turn your head to one side, then back", 4.0, 1.0),
    "angry": ("Make an angry face (frown) for ~1 s", 4.0, 1.0),
    "happy": ("Smile big, showing teeth, for ~1 s", 4.0, 1.0),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Calibrate the input thresholds for this person and session")
    parser.add_argument("--stream", default=DEFAULT_STREAM_NAME, help="Unicorn raw LSL stream name")
    parser.add_argument("--reps", type=int, default=6, help="Repetitions per input")
    parser.add_argument("--inputs", default=",".join(PRIORITY), help="Comma-separated inputs to calibrate")
    parser.add_argument("--analyze", type=Path, help="Calibrate from a saved session folder (no headset)")
    parser.add_argument("--recordings", type=Path, help="Calibrate from the 2026-10-04 recordings folder")
    parser.add_argument("--out", type=Path, default=calibration.DEFAULT_PATH, help="Where to save the thresholds")
    return parser.parse_args()


# ---------------------------------------------------------------------------------------------------------------
# Recording
# ---------------------------------------------------------------------------------------------------------------
class Recorder:
    def __init__(self, stream: str) -> None:
        from pylsl import StreamInlet, resolve_byprop

        print(f"Looking for LSL stream '{stream}'...")
        found = resolve_byprop("name", stream, timeout=8.0)
        if not found:
            raise SystemExit(f"No LSL stream named '{stream}'. Open Unicorn Recorder and turn on LSL.")
        self.inlet = StreamInlet(found[0], max_buflen=60)
        print(f"Connected ({found[0].channel_count()} channels)\n")

    def record(self, seconds: float, prompts: list[tuple[float, str]]) -> np.ndarray:
        """Pull samples for `seconds`, printing each prompt at its time offset."""
        self.inlet.pull_chunk(timeout=0.0, max_samples=100000)  # drop what queued during the instructions
        rows: list[list[float]] = []
        start = time.monotonic()
        pending = list(prompts)
        while (elapsed := time.monotonic() - start) < seconds:
            while pending and elapsed >= pending[0][0]:
                print(pending.pop(0)[1], flush=True)
            samples, _ = self.inlet.pull_chunk(timeout=0.05, max_samples=256)
            rows.extend(samples)
        return np.asarray(rows, dtype=np.float64)[:, :CSV_COLUMNS]


def save_rows(path: Path, rows: np.ndarray) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["timestamp", *[f"ch{i}" for i in range(CSV_COLUMNS)]])
        for i, row in enumerate(rows):
            writer.writerow([f"{i / SAMPLE_RATE:.4f}", *row])


def record_session(args: argparse.Namespace, inputs: tuple[str, ...]) -> Path:
    session = SESSIONS_DIR / datetime.now().strftime("session_%Y%m%d_%H%M%S")
    session.mkdir(parents=True, exist_ok=True)
    recorder = Recorder(args.stream)

    print(f"Step 1/{len(inputs) + 1}: REST. Sit still, eyes open, relaxed, for {REST_S:.0f} s.")
    input("Press Enter to start...")
    save_rows(session / "rest.csv", recorder.record(SETTLE_S + REST_S, [(SETTLE_S, "  recording rest...")]))

    for step, name in enumerate(inputs, start=2):
        text, period, held = STEPS[name]
        print(f"\nStep {step}/{len(inputs) + 1}: {name.upper()}  -  {text}.")
        print(f"  {args.reps} times, when you see  >>> NOW. Relax completely between them.")
        input("Press Enter to start...")
        prompts = []
        for rep in range(args.reps):
            at = SETTLE_S + rep * period
            prompts.append((at, f"  >>> NOW ({rep + 1}/{args.reps})\a"))
            if name == "cerrar_ojos":
                prompts.append((at + held, "      open your eyes"))
        seconds = SETTLE_S + args.reps * period + 1.0
        save_rows(session / f"{name}.csv", recorder.record(seconds, [(1.0, "  get ready..."), *prompts]))
    print(f"\nSaved the session to {session}")
    return session


# ---------------------------------------------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------------------------------------------
def session_segments(folder: Path, inputs: tuple[str, ...], reps: int) -> tuple[dict, dict, dict]:
    """Saved session -> (rows per segment, own segments per input, repetitions per segment)."""
    rows = {label: load_csv(folder / f"{label}.csv")[int(SETTLE_S * SAMPLE_RATE) :] for label in ("rest", *inputs)}
    return rows, {name: (name,) for name in inputs}, {name: reps for name in inputs}


def recording_segments(folder: Path) -> tuple[dict, dict, dict]:
    """The 2026-10-04 recordings -> the same three things, using check_all's file table."""
    rows, reps = {}, {}
    for label, (pattern, count) in RECORDINGS.items():
        path = find(folder, pattern)
        if path is not None:
            settle = 10.0 if label in ("rest", "ojos_cerrados_base") else SETTLE_S
            rows[label] = load_csv(path)[int(settle * SAMPLE_RATE) :]
            reps[label] = count
    return rows, dict(OWN), reps


def analyze(rows: dict, own: dict, reps: dict, inputs: tuple[str, ...], out: Path, note: str) -> None:
    print("\nPreparing the session...")
    segments = {label: segment(data, inputs) for label, data in rows.items()}
    gates = None
    if "angry" in inputs or "happy" in inputs:
        print("Fitting the face patterns to you...")
        gates = calibration.fit_face_limits(segments, own)
        calibration.apply_gates(gates)
    print("Choosing thresholds (replays the whole session through the arbiter, ~1-2 min)...")
    thresholds = calibration.choose_thresholds(segments, inputs, own, reps)
    path = calibration.save(thresholds, out, note, gates)

    print(f"\n  {'input':12s} {'tested':>8s} {'yours':>8s}")
    for name in inputs:
        print(f"  {name:12s} {calibration.ARTIFACT_PARAMS[name].threshold:8.2f} {thresholds[name]:8.2f}")
    print(f"\nSaved {path}")

    params = calibration.calibrated_params(path)
    print("\nHow the flight reads the session now (rows: what you did; columns: what it emitted):")
    print(f"  {'did':20s}" + "".join(f"{n[:9]:>10s}" for n in inputs))
    for label, seg in segments.items():
        counts = calibration.replay(seg, inputs, params)
        cells = "".join(f"{counts[n]:>9d}{'*' if label in own[n] else ' '}" for n in inputs)
        print(f"  {label:20s}{cells}" + (f"   (did {reps[label]})" if reps.get(label) else ""))
    print("\n* = should match. Anything else in a row is a confusion; 'rest' should be all zero.")
    print("If an input still misses or confuses, redo just that one: --inputs <name> (the others keep their values).")


def main() -> None:
    args = parse_args()
    inputs = tuple(name for name in PRIORITY if name in args.inputs.split(","))
    if args.recordings:
        rows, own, reps = recording_segments(args.recordings)
        own = {name: own[name] for name in inputs}
        note = f"from recordings in {args.recordings}"
    else:
        folder = args.analyze or record_session(args, inputs)
        rows, own, reps = session_segments(folder, inputs, args.reps)
        note = f"session {folder.name}"
    analyze(rows, own, reps, inputs, args.out, note)


if __name__ == "__main__":
    main()
