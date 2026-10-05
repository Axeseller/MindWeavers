"""Replay every recording through every artifact detector and print how many times each one fires.

    python scripts/artifacts/check_all.py <folder with the CSV recordings>

Diagonal = the artifact in its own recording (higher is better, up to the number of repetitions).
Off-diagonal and the rest / eyes-closed rows = false detections (should be 0).
"""

from __future__ import annotations

import argparse
from pathlib import Path

import _paths  # noqa: F401
from _live import detections, feature_series, load_csv
from eeg.detectors import ARTIFACT_PARAMS
from eeg.preprocess import SAMPLE_RATE

# Artifact -> recording file pattern, and how many repetitions the recording holds after the first 5 s.
RECORDINGS: dict[str, tuple[str, int]] = {
    "jaw": ("jaw_*.csv", 18),
    "blink": ("blink3sec*.csv", 18),
    "cerrar_ojos": ("cerrarojos*.csv", 9),
    "cuello_izq": ("cuelloizq*.csv", 14),
    "cuello_der": ("cuelloderecha*.csv", 14),
    "giro_imag_izq": ("girarcabezaimaginariaizq*.csv", 14),
    "giro_imag_der": ("girarcabezaimaginariader*.csv", 14),
    "enojado": ("enojado*.csv", 14),
    "happy": ("happyface*.csv", 14),
    "brazo_izq": ("brazoizq*.csv", 18),
    "puno_izq": ("pu*oizquierdo*.csv", 18),
    "puno_der": ("pu*oderecho*.csv", 18),
}
REFERENCES = {"rest": "rest_*.csv", "ojos_cerrados_base": "baselineojoscerrados*.csv"}
# Recorded but without a detector of their own; still checked for false detections.
OTHER_RECORDINGS = {"brazo_der": "brazoarriba*.csv"}
SETTLE_S = 5.0  # the headset settles during the first seconds of every recording
REFERENCE_SETTLE_S = 10.0  # rest and eyes-closed include cap adjustment up to ~10 s


def find(folder: Path, pattern: str) -> Path | None:
    """Largest file matching the pattern (an aborted recording leaves a tiny CSV)."""
    matches = sorted(folder.glob(pattern), key=lambda p: p.stat().st_size)
    return matches[-1] if matches else None


def main() -> None:
    parser = argparse.ArgumentParser(description="Detections of every artifact detector on every recording")
    parser.add_argument("folder", type=Path)
    parser.add_argument("--only", help="Comma-separated artifacts to check (default: all)")
    args = parser.parse_args()

    names = args.only.split(",") if args.only else list(ARTIFACT_PARAMS)
    sources = {**{n: pattern for n, (pattern, _) in RECORDINGS.items()}, **OTHER_RECORDINGS, **REFERENCES}
    rows = {}
    for label, pattern in sources.items():
        path = find(args.folder, pattern)
        if path is not None:
            settle = REFERENCE_SETTLE_S if label in REFERENCES else SETTLE_S
            rows[label] = load_csv(path)[int(settle * SAMPLE_RATE) :]

    print(f"{'recording':22s}" + "".join(f"{n[:9]:>10s}" for n in names))
    for label, data in rows.items():
        counts = []
        for name in names:
            times, values = feature_series(name, data)
            hits = len(detections(name, times, values))
            mark = "*" if name == label else " "
            counts.append(f"{hits:>9d}{mark}")
        expected = RECORDINGS.get(label, ("", 0))[1]
        print(f"{label:22s}" + "".join(counts) + (f"   (reps ~{expected})" if expected else ""))
    print("\n* = the detector's own recording")


if __name__ == "__main__":
    main()
