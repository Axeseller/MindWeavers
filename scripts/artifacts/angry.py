"""Angry face (frown).

Recording: enojadocada4sec. Signal: facial EMG 15-40 Hz; a jaw clench is 4x stronger and is discarded.
Cleaning: eeg.preprocess.ARTIFACT_CLEANING["angry"]. Decision: eeg.detectors.ARTIFACT_PARAMS["angry"].
Alone, this script only prints each detection. The drone action (LEFT pulse) runs from fly.py,
where the arbiter keeps the inputs from firing on each other.

    python scripts/artifacts/angry.py                  # headset LSL, Tello dry-run
    python scripts/artifacts/angry.py --replay <csv>   # recorded CSV, no hardware
"""

from __future__ import annotations

import _paths  # noqa: F401
from _live import run

ARTIFACT = "angry"

if __name__ == "__main__":
    run(ARTIFACT, "Angry face (frown) from the Unicorn LSL stream")
