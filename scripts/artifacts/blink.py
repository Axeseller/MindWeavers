"""Blink (parpadeo).

Recording: blink3secinterval. Signal: Fz, 0.5-8 Hz, signed peak: a blink is a one-way frontal deflection.
Cleaning: eeg.preprocess.ARTIFACT_CLEANING["blink"]. Decision: eeg.detectors.ARTIFACT_PARAMS["blink"].
On detection: Takes a photo if the camera is on (see camera.py to use it with cerrar_ojos).

    python scripts/artifacts/blink.py                  # headset LSL, Tello dry-run
    python scripts/artifacts/blink.py --live           # headset LSL, real Tello
    python scripts/artifacts/blink.py --replay <csv>   # recorded CSV, no hardware
"""

from __future__ import annotations

import _paths  # noqa: F401
from _live import run
from camera_actions import take_photo
from tello.controller import TelloController

ARTIFACT = "blink"


def on_detect(controller: TelloController) -> bool:
    """Drone action for this artifact. Return True to stop the script."""
    take_photo(controller)
    return False


if __name__ == "__main__":
    run(ARTIFACT, "Blink (parpadeo) from the Unicorn LSL stream", on_detect)
