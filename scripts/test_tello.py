from __future__ import annotations

import argparse
import time
from pathlib import Path

import _paths  # noqa: F401
from tello.controller import TelloController

PHOTO_DIR = Path(__file__).resolve().parents[1] / "data" / "recordings"


def main() -> None:
    parser = argparse.ArgumentParser(description="Tello smoke test: battery, takeoff, photo, land")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--hover", type=float, default=3.0, help="Seconds to hover before landing")
    args = parser.parse_args()

    controller = TelloController(dry_run=args.dry_run)
    if not controller.connect(with_video=True):
        raise SystemExit(1)

    try:
        controller.takeoff()
        print(f"Hovering {args.hover}s...")
        time.sleep(args.hover)
        controller.take_photo(PHOTO_DIR)
        controller.land()
    except KeyboardInterrupt:
        print("\nInterrupted — landing.")
    finally:
        controller.shutdown()


if __name__ == "__main__":
    main()
