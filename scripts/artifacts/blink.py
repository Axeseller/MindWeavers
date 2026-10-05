"""Blink: check this detector on its own.

Recording: blink3secinterval. Signal: Fz, 0.5-8 Hz, signed peak: a blink is a one-way frontal deflection.
Cleaning: eeg.preprocess.ARTIFACT_CLEANING["blink"]. Decision: eeg.detectors.ARTIFACT_PARAMS["blink"].
In the flight (src/app.py): S: back 1 s. This script only prints each detection.

    python scripts/artifacts/blink.py                  # headset LSL
    python scripts/artifacts/blink.py --threshold 20   # try another threshold
    python scripts/artifacts/blink.py --replay <csv>   # recorded CSV, no hardware
"""

from __future__ import annotations

import _paths  # noqa: F401
from _live import run

ARTIFACT = "blink"

if __name__ == "__main__":
    run(ARTIFACT, "Blink from the Unicorn LSL stream")
