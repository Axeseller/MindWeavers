"""Happy face (smile).

Recording: happyfacecada4sec. Signal: facial EMG 30-100 Hz after common average reference.
Cleaning: eeg.preprocess.ARTIFACT_CLEANING["happy"]. Decision: eeg.detectors.ARTIFACT_PARAMS["happy"].
Not mapped to a drone command yet: each detection is only printed. Put the command in on_detect().

    python scripts/artifacts/happy.py                  # headset LSL, Tello dry-run
    python scripts/artifacts/happy.py --live           # headset LSL, real Tello
    python scripts/artifacts/happy.py --replay <csv>   # recorded CSV, no hardware
"""

from __future__ import annotations

import _paths  # noqa: F401
from _live import run
from tello.controller import TelloController

ARTIFACT = "happy"


def on_detect(controller: TelloController) -> bool:
    """Drone action for this artifact. Return True to stop the script."""
    return False


if __name__ == "__main__":
    run(ARTIFACT, "Happy face (smile) from the Unicorn LSL stream", on_detect)
