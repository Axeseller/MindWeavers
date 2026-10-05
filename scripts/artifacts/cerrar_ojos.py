"""Eyes closed and held: check this detector on its own.

Recording: cerrarojos3secmantenido. Signal: occipital alpha 8-13 Hz held for 1.5 s.
Cleaning: eeg.preprocess.ARTIFACT_CLEANING["cerrar_ojos"]. Decision: eeg.detectors.ARTIFACT_PARAMS["cerrar_ojos"].
In the flight (src/app.py): turn 90 deg right. This script only prints each detection.

    python scripts/artifacts/cerrar_ojos.py                  # headset LSL
    python scripts/artifacts/cerrar_ojos.py --threshold 20   # try another threshold
    python scripts/artifacts/cerrar_ojos.py --replay <csv>   # recorded CSV, no hardware
"""

from __future__ import annotations

import _paths  # noqa: F401
from _live import run

ARTIFACT = "cerrar_ojos"

if __name__ == "__main__":
    run(ARTIFACT, "Eyes closed and held from the Unicorn LSL stream")
