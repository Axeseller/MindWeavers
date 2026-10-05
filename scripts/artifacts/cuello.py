"""Head turn (either side): check this detector on its own.

Recording: cuelloderechacada4sec / cuelloizqcada4sec. Signal: gyroscope yaw, either direction.
Cleaning: eeg.preprocess.ARTIFACT_CLEANING["cuello"]. Decision: eeg.detectors.ARTIFACT_PARAMS["cuello"].
In the flight (src/app.py): W: forward 1 s. This script only prints each detection.

    python scripts/artifacts/cuello.py                  # headset LSL
    python scripts/artifacts/cuello.py --threshold 20   # try another threshold
    python scripts/artifacts/cuello.py --replay <csv>   # recorded CSV, no hardware
"""

from __future__ import annotations

import _paths  # noqa: F401
from _live import run

ARTIFACT = "cuello"

if __name__ == "__main__":
    run(ARTIFACT, "Head turn (either side) from the Unicorn LSL stream")
