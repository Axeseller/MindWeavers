"""Imagined head turn to the right.

Recording: girarcabezaimaginariaderechacada4sec. Signal: gyroscope pitch, first movement positive (residual head motion, not pure EEG).
Cleaning: eeg.preprocess.ARTIFACT_CLEANING["giro_imag_der"]. Decision: eeg.detectors.ARTIFACT_PARAMS["giro_imag_der"].
Not mapped to a drone command yet: each detection is only printed. Put the command in on_detect().

    python scripts/artifacts/giro_imag_der.py                  # headset LSL, Tello dry-run
    python scripts/artifacts/giro_imag_der.py --live           # headset LSL, real Tello
    python scripts/artifacts/giro_imag_der.py --replay <csv>   # recorded CSV, no hardware
"""

from __future__ import annotations

import _paths  # noqa: F401
from _live import run
from tello.controller import TelloController

ARTIFACT = "giro_imag_der"


def on_detect(controller: TelloController) -> bool:
    """Drone action for this artifact. Return True to stop the script."""
    return False


if __name__ == "__main__":
    run(ARTIFACT, "Imagined head turn to the right from the Unicorn LSL stream", on_detect)
