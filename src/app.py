"""Deprecated compatibility entry point.

Use ``python scripts/artifacts/fly.py`` for the integrated artifact pipeline.
This wrapper keeps common legacy invocations working while the old, separate
jaw/blink loop is retired.
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = ROOT / "scripts" / "artifacts"
ARTIFACT_RUNNER = ARTIFACT_DIR / "fly.py"


def translate_legacy_args(argv: list[str]) -> list[str]:
    """Translate flags whose safe meaning is unchanged in the artifact runner."""
    translated: list[str] = []
    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg in ("--dry-run", "--no-video"):
            # fly.py is dry-run and camera-off by default.
            index += 1
            continue
        if arg == "--no-lsl":
            raise SystemExit(
                "src/app.py --no-lsl has been retired. "
                "Use `python scripts/manual_mode.py --no-eeg` for keyboard-only flight."
            )
        if arg == "--threshold":
            if index + 1 == len(argv):
                raise SystemExit("src/app.py --threshold requires a numeric value.")
            translated.extend(("--threshold", f"jaw={argv[index + 1]}"))
            index += 2
            continue
        if arg.startswith("--threshold="):
            translated.extend(("--threshold", f"jaw={arg.partition('=')[2]}"))
            index += 1
            continue
        translated.append(arg)
        index += 1
    return translated


def main(argv: list[str] | None = None) -> None:
    """Run the canonical artifact pipeline through the old command path."""
    print(
        "DEPRECATED: src/app.py now forwards to scripts/artifacts/fly.py. "
        "Update scripts and documentation to use the new path.",
        file=sys.stderr,
    )
    forwarded = translate_legacy_args(sys.argv[1:] if argv is None else argv)
    previous_argv, previous_path = sys.argv, list(sys.path)
    try:
        sys.argv = [str(ARTIFACT_RUNNER), *forwarded]
        sys.path.insert(0, str(ARTIFACT_DIR))
        runpy.run_path(str(ARTIFACT_RUNNER), run_name="__main__")
    finally:
        sys.argv = previous_argv
        sys.path[:] = previous_path


if __name__ == "__main__":
    main()
