"""Raise the left arm.

Recording: brazoizquierdo3sec. Signal: gyroscope yaw, first movement negative.
Cleaning: eeg.preprocess.ARTIFACT_CLEANING["brazo_izq"]. Decision: eeg.detectors.ARTIFACT_PARAMS["brazo_izq"].
Not mapped to a drone command yet: each detection is only printed. Put the command in on_detect().

    python scripts/artifacts/brazo_izq.py                  # headset LSL, Tello dry-run
    python scripts/artifacts/brazo_izq.py --live           # headset LSL, real Tello
    python scripts/artifacts/brazo_izq.py --replay <csv>   # recorded CSV, no hardware
"""

from __future__ import annotations

import _paths  # noqa: F401
from _live import run
from tello.controller import TelloController

ARTIFACT = "brazo_izq"


def on_detect(controller: TelloController) -> bool:
    """Drone action for this artifact. Return True to stop the script."""
    return False


if __name__ == "__main__":
    run(ARTIFACT, "Raise the left arm from the Unicorn LSL stream", on_detect)
