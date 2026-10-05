"""Angry face (frown).

Recording: enojadocada4sec. Signal: facial EMG 15-40 Hz on all 8 channels.
Cleaning: eeg.preprocess.ARTIFACT_CLEANING["enojado"]. Decision: eeg.detectors.ARTIFACT_PARAMS["enojado"].
Not mapped to a drone command yet: each detection is only printed. Put the command in on_detect().

    python scripts/artifacts/enojado.py                  # headset LSL, Tello dry-run
    python scripts/artifacts/enojado.py --live           # headset LSL, real Tello
    python scripts/artifacts/enojado.py --replay <csv>   # recorded CSV, no hardware
"""

from __future__ import annotations

import _paths  # noqa: F401
from _live import run
from tello.controller import TelloController

ARTIFACT = "enojado"


def on_detect(controller: TelloController) -> bool:
    """Drone action for this artifact. Return True to stop the script."""
    return False


if __name__ == "__main__":
    run(ARTIFACT, "Angry face (frown) from the Unicorn LSL stream", on_detect)
