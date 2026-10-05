"""Angry face (frown): check this detector on its own.

Recording: enojadocada4sec. Signal: facial EMG 15-40 Hz with the frown's frontal/occipital pattern.
Cleaning: eeg.preprocess.ARTIFACT_CLEANING["angry"]. Decision: eeg.detectors.ARTIFACT_PARAMS["angry"].
In the flight (src/app.py): A: left 1 s. This script only prints each detection.

    python scripts/artifacts/angry.py                  # headset LSL
    python scripts/artifacts/angry.py --threshold 20   # try another threshold
    python scripts/artifacts/angry.py --replay <csv>   # recorded CSV, no hardware
"""

from __future__ import annotations

import _paths  # noqa: F401
from _live import run

ARTIFACT = "angry"

if __name__ == "__main__":
    run(ARTIFACT, "Angry face (frown) from the Unicorn LSL stream")
