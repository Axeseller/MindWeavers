"""Raise an arm (either).

Recording: brazoizquierdo3sec / brazoarriba3sec. Signal: gyroscope pitch, first movement negative.
Cleaning: eeg.preprocess.ARTIFACT_CLEANING["brazos"]. Decision: eeg.detectors.ARTIFACT_PARAMS["brazos"].
Alone, this script only prints each detection. The drone action (FORWARD pulse) runs from fly.py,
where the arbiter keeps the inputs from firing on each other.

    python scripts/artifacts/brazos.py                  # headset LSL, Tello dry-run
    python scripts/artifacts/brazos.py --replay <csv>   # recorded CSV, no hardware
"""

from __future__ import annotations

import _paths  # noqa: F401
from _live import run

ARTIFACT = "brazos"

if __name__ == "__main__":
    run(ARTIFACT, "Raise an arm (either) from the Unicorn LSL stream")
