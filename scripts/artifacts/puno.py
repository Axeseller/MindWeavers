"""Close a fist (either): check this detector on its own.

Recording: puñoizquierdo3sec / puñoderecho3sec. Signal: small gyroscope movement; anything big is a neck or arm move and is discarded.
Cleaning: eeg.preprocess.ARTIFACT_CLEANING["puno"]. Decision: eeg.detectors.ARTIFACT_PARAMS["puno"].
In the flight (src/app.py): not used (the weakest input). This script only prints each detection.

    python scripts/artifacts/puno.py                  # headset LSL
    python scripts/artifacts/puno.py --threshold 20   # try another threshold
    python scripts/artifacts/puno.py --replay <csv>   # recorded CSV, no hardware
"""

from __future__ import annotations

import _paths  # noqa: F401
from _live import run

ARTIFACT = "puno"

if __name__ == "__main__":
    run(ARTIFACT, "Close a fist (either) from the Unicorn LSL stream")
