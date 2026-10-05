"""Happy face (smile): check this detector on its own.

Recording: happyfacecada4sec. Signal: facial EMG 30-100 Hz after removing what all electrodes share.
Cleaning: eeg.preprocess.ARTIFACT_CLEANING["happy"]. Decision: eeg.detectors.ARTIFACT_PARAMS["happy"].
In the flight (src/app.py): D: right 1 s. This script only prints each detection.

    python scripts/artifacts/happy.py                  # headset LSL
    python scripts/artifacts/happy.py --threshold 20   # try another threshold
    python scripts/artifacts/happy.py --replay <csv>   # recorded CSV, no hardware
"""

from __future__ import annotations

import _paths  # noqa: F401
from _live import run

ARTIFACT = "happy"

if __name__ == "__main__":
    run(ARTIFACT, "Happy face (smile) from the Unicorn LSL stream")
