"""Jaw clench -> takeoff. The one artifact already mapped to the drone.

Recording: jaw. Signal: EMG 15-40 Hz on all 8 channels, clench held 0.5-2 s (the original jaw takeoff detector).
Cleaning: eeg.preprocess.ARTIFACT_CLEANING["jaw"]. Decision: eeg.detectors.ARTIFACT_PARAMS["jaw"].
On detection: take off, hover, land, exit. In the flight (src/app.py): Q takeoff / E land.

    python scripts/artifacts/jaw.py                  # headset LSL, Tello dry-run
    python scripts/artifacts/jaw.py --live           # headset LSL, real Tello
    python scripts/artifacts/jaw.py --replay <csv>   # recorded CSV, no hardware
"""

from __future__ import annotations

import time

import _paths  # noqa: F401
from _live import run
from tello.controller import TelloController

ARTIFACT = "jaw"
HOVER_SECONDS = 8.0
HOVER_TICK_S = 0.1


def on_detect(controller: TelloController) -> bool:
    """Take off, hover in place, then land. Returns True: one flight per run."""
    controller.takeoff()
    print(f"Hovering for {HOVER_SECONDS:.0f} s...")
    end = time.monotonic() + HOVER_SECONDS
    while time.monotonic() < end:
        controller.hover()
        time.sleep(HOVER_TICK_S)
    controller.land()
    print("Mission complete.")
    return True


if __name__ == "__main__":
    run(ARTIFACT, "Take off the Tello with one jaw clench (Unicorn LSL)", on_detect)
