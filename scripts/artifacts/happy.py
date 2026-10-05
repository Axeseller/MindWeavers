"""Happy face (smile).

Recording: happyfacecada4sec. Signal: facial EMG 30-100 Hz after removing what all electrodes share.
Cleaning: eeg.preprocess.ARTIFACT_CLEANING["happy"]. Decision: eeg.detectors.ARTIFACT_PARAMS["happy"].
Alone, this script only prints each detection. The drone action (FORWARD pulse) runs from fly.py,
where the arbiter keeps the inputs from firing on each other.

    python scripts/artifacts/happy.py                  # headset LSL, Tello dry-run
    python scripts/artifacts/happy.py --replay <csv>   # recorded CSV, no hardware
"""

from __future__ import annotations

import _paths  # noqa: F401
from _live import run

ARTIFACT = "happy"

if __name__ == "__main__":
    run(ARTIFACT, "Happy face (smile) from the Unicorn LSL stream")
