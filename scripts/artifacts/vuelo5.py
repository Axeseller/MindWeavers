"""Simple flight with five inputs, ready for the real Tello. A copy of vuelo.py's flight plus left and right:

    jaw (1st time)  -> Q  takeoff
    cuello          -> W  forward 1 s   (turn the head to either side, then back)
    blink           -> S  back 1 s
    happy (smile)   -> D  right 1 s
    angry (frown)   -> A  left 1 s
    jaw (2nd time)  -> E  land

vuelo.py is untouched: use it when only jaw, neck and blink are wanted. Same detectors, arbiter and calibration:

    python scripts/artifacts/calibrate.py --inputs jaw,cuello,blink,angry,happy
    python scripts/artifacts/vuelo5.py --dry-run               # no drone, prints what it would send
    python scripts/artifacts/vuelo5.py                         # REAL Tello: connect to its Wi-Fi first
    python scripts/artifacts/vuelo5.py --replay <csv> --dry-run

Ctrl+C lands and exits at any time. Keep the eyes open while flying.
"""

from __future__ import annotations

import _paths  # noqa: F401
import vuelo

INPUTS = ("jaw", "cuello", "blink", "angry", "happy")
KEYS = {"cuello": "w", "blink": "s", "happy": "d", "angry": "a"}
CONTROLS = (
    "  JAW clench   -> Q takeoff (1st) / E land (2nd)",
    "  Turn head   -> W forward (either side)",
    "  BLINK       -> S back",
    "  SMILE       -> D right",
    "  FROWN       -> A left",
)

if __name__ == "__main__":
    vuelo.main(INPUTS, KEYS, CONTROLS)
