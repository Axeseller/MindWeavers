"""Real head turn to the right.

Recording: cuelloderechacada4sec. Signal: gyroscope yaw, first movement negative.
Cleaning: eeg.preprocess.ARTIFACT_CLEANING["cuello_der"]. Decision: eeg.detectors.ARTIFACT_PARAMS["cuello_der"].
Not mapped to a drone command yet: each detection is only printed. Put the command in on_detect().

    python scripts/artifacts/cuello_der.py                  # headset LSL, Tello dry-run
    python scripts/artifacts/cuello_der.py --live           # headset LSL, real Tello
    python scripts/artifacts/cuello_der.py --replay <csv>   # recorded CSV, no hardware
"""

from __future__ import annotations

import _paths  # noqa: F401
from _live import run
from tello.controller import TelloController

ARTIFACT = "cuello_der"


def on_detect(controller: TelloController) -> bool:
    """Drone action for this artifact. Return True to stop the script."""
    return False


if __name__ == "__main__":
    run(ARTIFACT, "Real head turn to the right from the Unicorn LSL stream", on_detect)
