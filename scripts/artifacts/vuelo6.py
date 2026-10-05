"""Simple flight with six inputs, ready for the real Tello. vuelo5.py's flight plus an exact 90° turn:

    jaw (1st time)      -> Q  takeoff
    cuello              -> W  forward 1 s   (turn the head to either side, then back)
    blink               -> S  back 1 s
    happy (smile)       -> D  right 1 s
    angry (frown)       -> A  left 1 s
    cerrar_ojos         -> turn 90° to the right (tello.rotate_clockwise), once per closure
    jaw (2nd time)      -> E  land

vuelo.py and vuelo5.py are untouched. Same detectors, arbiter and calibration:

    python scripts/artifacts/calibrate.py --inputs jaw,cerrar_ojos,cuello,blink,angry,happy
    python scripts/artifacts/vuelo6.py --dry-run               # no drone, prints what it would send
    python scripts/artifacts/vuelo6.py                         # REAL Tello: connect to its Wi-Fi first

Keep the eyes closed ~1.5 s to turn; open them before closing again for another turn. Ctrl+C lands and exits.
"""

from __future__ import annotations

import _paths  # noqa: F401
import vuelo

INPUTS = ("jaw", "cerrar_ojos", "cuello", "blink", "angry", "happy")
KEYS = {"cuello": "w", "blink": "s", "happy": "d", "angry": "a"}
TURNS = {"cerrar_ojos": 90}
CONTROLS = (
    "  JAW clench   -> Q takeoff (1st) / E land (2nd)",
    "  Turn head   -> W forward (either side)",
    "  BLINK       -> S back",
    "  SMILE       -> D right",
    "  FROWN       -> A left",
    "  EYES CLOSED -> turn 90 deg right (~1.5 s, open them before the next one)",
)

if __name__ == "__main__":
    vuelo.main(INPUTS, KEYS, CONTROLS, TURNS)
