"""Close the left fist.

Recording: puñoizquierdo3sec. Signal: gyroscope magnitude; cannot tell left from right fist.
Cleaning: eeg.preprocess.ARTIFACT_CLEANING["puno_izq"]. Decision: eeg.detectors.ARTIFACT_PARAMS["puno_izq"].
Not mapped to a drone command yet: each detection is only printed. Put the command in on_detect().

    python scripts/artifacts/puno_izq.py                  # headset LSL, Tello dry-run
    python scripts/artifacts/puno_izq.py --live           # headset LSL, real Tello
    python scripts/artifacts/puno_izq.py --replay <csv>   # recorded CSV, no hardware
"""

from __future__ import annotations

import _paths  # noqa: F401
from _live import run
from tello.controller import TelloController

ARTIFACT = "puno_izq"


def on_detect(controller: TelloController) -> bool:
    """Drone action for this artifact. Return True to stop the script."""
    return False


if __name__ == "__main__":
    run(ARTIFACT, "Close the left fist from the Unicorn LSL stream", on_detect)
