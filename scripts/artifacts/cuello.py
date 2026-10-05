"""Head turn to the right.

Recording: cuelloderechacada4sec. Signal: gyroscope yaw, first movement negative.
Cleaning: eeg.preprocess.ARTIFACT_CLEANING["cuello"]. Decision: eeg.detectors.ARTIFACT_PARAMS["cuello"].
Alone, this script only prints each detection. The drone action (RIGHT pulse) runs from fly.py,
where the arbiter keeps the inputs from firing on each other.

    python scripts/artifacts/cuello.py                  # headset LSL, Tello dry-run
    python scripts/artifacts/cuello.py --replay <csv>   # recorded CSV, no hardware
"""

from __future__ import annotations

import _paths  # noqa: F401
from _live import run

ARTIFACT = "cuello"

if __name__ == "__main__":
    run(ARTIFACT, "Head turn to the right from the Unicorn LSL stream")
