"""Real head turn to the left.

Recording: cuelloizqcada4sec. Signal: gyroscope yaw, first movement positive.
Cleaning: eeg.preprocess.ARTIFACT_CLEANING["cuello_izq"]. Decision: eeg.detectors.ARTIFACT_PARAMS["cuello_izq"].
Not mapped to a drone command yet: each detection is only printed. Put the command in on_detect().

    python scripts/artifacts/cuello_izq.py                  # headset LSL, Tello dry-run
    python scripts/artifacts/cuello_izq.py --live           # headset LSL, real Tello
    python scripts/artifacts/cuello_izq.py --replay <csv>   # recorded CSV, no hardware
"""

from __future__ import annotations

import _paths  # noqa: F401
from _live import run
from tello.controller import TelloController

ARTIFACT = "cuello_izq"


def on_detect(controller: TelloController) -> bool:
    """Drone action for this artifact. Return True to stop the script."""
    return False


if __name__ == "__main__":
    run(ARTIFACT, "Real head turn to the left from the Unicorn LSL stream", on_detect)
