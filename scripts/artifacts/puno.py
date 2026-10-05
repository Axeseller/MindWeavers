"""Close a fist (either).

Recording: puñoizquierdo3sec / puñoderecho3sec. Signal: small gyroscope movement; anything big is a neck or arm move and is discarded.
Cleaning: eeg.preprocess.ARTIFACT_CLEANING["puno"]. Decision: eeg.detectors.ARTIFACT_PARAMS["puno"].
Alone, this script only prints each detection. The drone action (BACK pulse) runs from fly.py,
where the arbiter keeps the inputs from firing on each other.

    python scripts/artifacts/puno.py                  # headset LSL, Tello dry-run
    python scripts/artifacts/puno.py --replay <csv>   # recorded CSV, no hardware
"""

from __future__ import annotations

import _paths  # noqa: F401
from _live import run

ARTIFACT = "puno"

if __name__ == "__main__":
    run(ARTIFACT, "Close a fist (either) from the Unicorn LSL stream")
