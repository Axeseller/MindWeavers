"""Replay every recording through every input and print how often each one fires.

    python scripts/artifacts/check_all.py <folder with the CSV recordings>

Two tables:
1. Each detector alone (what the single-input scripts do). Off-diagonal numbers are crossovers.
2. The arbiter (what fly.py does): only one input per gesture, so crossovers should be gone.
`*` marks the recording(s) of that input; `rest` and `ojos_cerrados_base` should be all zero.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import _paths  # noqa: F401
from _live import detections, feature_series, load_csv
from eeg.arbiter import PRIORITY, InputArbiter
from eeg.preprocess import SAMPLE_RATE

# Recording label -> (file pattern, repetitions in it)
RECORDINGS: dict[str, tuple[str, int]] = {
    "jaw": ("jaw_*.csv", 18),
    "blink": ("blink3sec*.csv", 18),
    "cerrar_ojos": ("cerrarojos*.csv", 9),
    "cuello_der": ("cuelloderecha*.csv", 14),
    "cuello_izq": ("cuelloizq*.csv", 14),
    "brazo_izq": ("brazoizq*.csv", 18),
    "brazo_der": ("brazoarriba*.csv", 18),
    "puno_izq": ("pu*oizquierdo*.csv", 18),
    "puno_der": ("pu*oderecho*.csv", 18),
    "angry": ("enojado*.csv", 14),
    "happy": ("happyface*.csv", 14),
    "giro_imag_izq": ("girarcabezaimaginariaizq*.csv", 14),
    "giro_imag_der": ("girarcabezaimaginariader*.csv", 14),
    "rest": ("rest_*.csv", 0),
    "ojos_cerrados_base": ("baselineojoscerrados*.csv", 0),
}
# Input -> the recordings where it is the gesture being done
OWN: dict[str, tuple[str, ...]] = {
    "jaw": ("jaw",),
    "blink": ("blink",),
    "cerrar_ojos": ("cerrar_ojos",),
    "cuello": ("cuello_der",),
    "brazos": ("brazo_izq", "brazo_der"),
    "puno": ("puno_izq", "puno_der"),
    "angry": ("angry",),
}
SETTLE_S = 5.0  # the headset settles during the first seconds of every recording
REFERENCE_SETTLE_S = 10.0  # rest and eyes-closed include cap adjustment up to ~10 s
TICK_S = 10 / SAMPLE_RATE


def find(folder: Path, pattern: str) -> Path | None:
    """Largest file matching the pattern (an aborted recording leaves a tiny CSV)."""
    matches = sorted(folder.glob(pattern), key=lambda p: p.stat().st_size)
    return matches[-1] if matches else None


def arbiter_counts(series: dict[str, tuple], inputs: tuple[str, ...], motion: tuple, emg: tuple) -> dict[str, int]:
    arbiter = InputArbiter(inputs)
    counts = {name: 0 for name in inputs}
    times = series[inputs[0]][0]
    for i, now in enumerate(times):
        values = {name: float(series[name][1][i]) for name in inputs}
        confirmed = arbiter.update(values, float(now), motion=float(motion[1][i]), emg=float(emg[1][i]))
        if confirmed:
            counts[confirmed] += 1
    return counts


def print_table(title: str, names: tuple[str, ...], rows: dict[str, dict[str, int]]) -> None:
    print(f"\n{title}")
    print(f"{'recording':20s}" + "".join(f"{n[:11]:>12s}" for n in names))
    for label, counts in rows.items():
        cells = "".join(f"{counts[n]:>11d}{'*' if label in OWN.get(n, ()) else ' '}" for n in names)
        reps = RECORDINGS[label][1]
        print(f"{label:20s}{cells}" + (f"   (reps ~{reps})" if reps else ""))


def main() -> None:
    parser = argparse.ArgumentParser(description="Every input on every recording, alone and through the arbiter")
    parser.add_argument("folder", type=Path)
    parser.add_argument("--only", help="Comma-separated inputs to check (default: all)")
    args = parser.parse_args()
    names = tuple(args.only.split(",")) if args.only else PRIORITY

    alone: dict[str, dict[str, int]] = {}
    together: dict[str, dict[str, int]] = {}
    for label, (pattern, _reps) in RECORDINGS.items():
        path = find(args.folder, pattern)
        if path is None:
            continue
        settle = REFERENCE_SETTLE_S if label in ("rest", "ojos_cerrados_base") else SETTLE_S
        rows = load_csv(path)[int(settle * SAMPLE_RATE) :]
        series = {name: feature_series(name, rows) for name in names}
        motion = series.get("puno") or feature_series("puno", rows)
        emg = series.get("jaw") or feature_series("jaw", rows)
        alone[label] = {name: len(detections(name, *series[name])) for name in names}
        together[label] = arbiter_counts(series, names, motion, emg)

    print_table("1. Each detector alone", names, alone)
    print_table("2. Through the arbiter (fly.py)", names, together)
    print("\n* = that input's own recording")


if __name__ == "__main__":
    main()
