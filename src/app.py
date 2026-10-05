"""Main entry point: flight with the Unicorn, through Tello/Mover.py (scripts/artifacts/vuelo6.py).

    jaw clench (1st)   -> Q: takeoff
    turn the head      -> W: forward 1 s (either side)
    blink              -> S: back 1 s
    smile (happy)      -> D: right 1 s
    frown (angry)      -> A: left 1 s
    eyes closed ~1.5 s -> turn 90° right
    jaw clench (2nd)   -> E: land

    python src/app.py --dry-run     # no drone: prints what it would send
    python src/app.py               # REAL Tello (connect to its Wi-Fi first); Ctrl+C lands

Fewer inputs, if some do not read well for the pilot:
    python src/app.py --lados       # without the eyes-closed turn (vuelo5.py)
    python src/app.py --simple      # only jaw, neck and blink (vuelo.py)

Calibrate once per person and session:
`python scripts/artifacts/calibrate.py --inputs jaw,cerrar_ojos,cuello,blink,angry,happy`.
This file also translates the flags of the old app.py.
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = ROOT / "scripts" / "artifacts"
FLIGHT_SIMPLE = ARTIFACT_DIR / "vuelo.py"
FLIGHT_SIDES = ARTIFACT_DIR / "vuelo5.py"
FLIGHT_TURN = ARTIFACT_DIR / "vuelo6.py"
FLIGHT = FLIGHT_TURN  # the default: all six inputs
CHOICES = {"--simple": FLIGHT_SIMPLE, "--lados": FLIGHT_SIDES, "--giro": FLIGHT_TURN}


def translate_legacy_args(argv: list[str]) -> list[str]:
    """Translate the flags of the old app.py into vuelo.py's."""
    translated: list[str] = []
    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg in CHOICES:  # handled by pick_flight()
            index += 1
            continue
        if arg == "--no-video":
            # vuelo.py never uses the camera.
            index += 1
            continue
        if arg == "--no-lsl":
            raise SystemExit(
                "src/app.py --no-lsl has been retired. "
                "Use `python scripts/manual_mode.py --no-eeg` for keyboard-only flight."
            )
        if arg == "--threshold":
            if index + 1 == len(argv):
                raise SystemExit("src/app.py --threshold requires a value: 40 (jaw) or INPUT=VALUE.")
            translated.extend(("--threshold", _threshold(argv[index + 1])))
            index += 2
            continue
        if arg.startswith("--threshold="):
            translated.extend(("--threshold", _threshold(arg.partition("=")[2])))
            index += 1
            continue
        translated.append(arg)
        index += 1
    return translated


def _threshold(value: str) -> str:
    """A bare number is the old app.py's jaw threshold; INPUT=VALUE passes through (happy=1.5, angry=4)."""
    return value if "=" in value else f"jaw={value}"


def pick_flight(args: list[str]) -> Path:
    """--simple / --lados choose a smaller flight; otherwise all six inputs."""
    for flag, path in CHOICES.items():
        if flag in args:
            return path
    return FLIGHT


def main(argv: list[str] | None = None) -> None:
    """Run the simple flight."""
    for stream in (sys.stdout, sys.stderr):  # see scripts/artifacts/_paths.py: Git Bash would buffer the output
        try:
            stream.reconfigure(line_buffering=True)
        except (AttributeError, ValueError):
            pass
    args = sys.argv[1:] if argv is None else argv
    flight = pick_flight(args)
    forwarded = translate_legacy_args(args)
    previous_argv, previous_path = sys.argv, list(sys.path)
    try:
        sys.argv = [str(flight), *forwarded]
        sys.path.insert(0, str(ARTIFACT_DIR))
        runpy.run_path(str(flight), run_name="__main__")
    finally:
        sys.argv = previous_argv
        sys.path[:] = previous_path


if __name__ == "__main__":
    main()
