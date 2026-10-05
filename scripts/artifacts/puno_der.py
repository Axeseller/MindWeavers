"""Close the right fist.

Recording: puñoderecho3sec. Signal: gyroscope magnitude; cannot tell left from right fist.
Cleaning: eeg.preprocess.ARTIFACT_CLEANING["puno_der"]. Decision: eeg.detectors.ARTIFACT_PARAMS["puno_der"].
Proposed command: UP (replaces raising the right arm). Either fist triggers it: no signal tells them apart.
Not mapped to a drone command yet: each detection is only printed. Put the command in on_detect().

    python scripts/artifacts/puno_der.py                  # headset LSL, Tello dry-run
    python scripts/artifacts/puno_der.py --live           # headset LSL, real Tello
    python scripts/artifacts/puno_der.py --replay <csv>   # recorded CSV, no hardware
"""

from __future__ import annotations

import _paths  # noqa: F401
from _live import run
from tello.controller import TelloController

ARTIFACT = "puno_der"


def on_detect(controller: TelloController) -> bool:
    """Drone action for this artifact. Return True to stop the script."""
    return False


if __name__ == "__main__":
    run(ARTIFACT, "Close the right fist from the Unicorn LSL stream", on_detect)
