"""Raise the right arm.

Recording: brazoarriba3sec. Signal: gyroscope yaw, first movement positive.
Cleaning: eeg.preprocess.ARTIFACT_CLEANING["brazo_der"]. Decision: eeg.detectors.ARTIFACT_PARAMS["brazo_der"].
Not mapped to a drone command yet: each detection is only printed. Put the command in on_detect().

    python scripts/artifacts/brazo_der.py                  # headset LSL, Tello dry-run
    python scripts/artifacts/brazo_der.py --live           # headset LSL, real Tello
    python scripts/artifacts/brazo_der.py --replay <csv>   # recorded CSV, no hardware
"""

from __future__ import annotations

import _paths  # noqa: F401
from _live import run
from tello.controller import TelloController

ARTIFACT = "brazo_der"


def on_detect(controller: TelloController) -> bool:
    """Drone action for this artifact. Return True to stop the script."""
    return False


if __name__ == "__main__":
    run(ARTIFACT, "Raise the right arm from the Unicorn LSL stream", on_detect)
