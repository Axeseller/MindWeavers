"""Eyes closed and held (cerrar ojos).

Recording: cerrarojos3secmantenido. Signal: occipital alpha 8-13 Hz held for 1.5 s.
Cleaning: eeg.preprocess.ARTIFACT_CLEANING["cerrar_ojos"]. Decision: eeg.detectors.ARTIFACT_PARAMS["cerrar_ojos"].
Not mapped to a drone command yet: each detection is only printed. Put the command in on_detect().

    python scripts/artifacts/cerrar_ojos.py                  # headset LSL, Tello dry-run
    python scripts/artifacts/cerrar_ojos.py --live           # headset LSL, real Tello
    python scripts/artifacts/cerrar_ojos.py --replay <csv>   # recorded CSV, no hardware
"""

from __future__ import annotations

import _paths  # noqa: F401
from _live import run
from tello.controller import TelloController

ARTIFACT = "cerrar_ojos"


def on_detect(controller: TelloController) -> bool:
    """Drone action for this artifact. Return True to stop the script."""
    return False


if __name__ == "__main__":
    run(ARTIFACT, "Eyes closed and held (cerrar ojos) from the Unicorn LSL stream", on_detect)
