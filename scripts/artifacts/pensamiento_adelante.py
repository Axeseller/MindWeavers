"""Think 'forward'.

Recording: pensamientoadelante. Signal: occipital alpha held; in practice this is the eyes-closed state.
Cleaning: eeg.preprocess.ARTIFACT_CLEANING["pensamiento_adelante"]. Decision: eeg.detectors.ARTIFACT_PARAMS["pensamiento_adelante"].
Not mapped to a drone command yet: each detection is only printed. Put the command in on_detect().

    python scripts/artifacts/pensamiento_adelante.py                  # headset LSL, Tello dry-run
    python scripts/artifacts/pensamiento_adelante.py --live           # headset LSL, real Tello
    python scripts/artifacts/pensamiento_adelante.py --replay <csv>   # recorded CSV, no hardware
"""

from __future__ import annotations

import _paths  # noqa: F401
from _live import run
from tello.controller import TelloController

ARTIFACT = "pensamiento_adelante"


def on_detect(controller: TelloController) -> bool:
    """Drone action for this artifact. Return True to stop the script."""
    return False


if __name__ == "__main__":
    run(ARTIFACT, "Think 'forward' from the Unicorn LSL stream", on_detect)
