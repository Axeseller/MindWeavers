from __future__ import annotations

import argparse
import time

import _paths  # noqa: F401
from tello import skills
from tello.controller import TelloController, print_keyboard_help

LOOP_SLEEP_S = 0.01
KEY_NONE = 255
KEY_ESC = 27
KEY_SPACE = 32


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manual_Mode: free keyboard controller for the Tello basic skills")
    parser.add_argument("--live", action="store_true", help="Connect to the real Tello (default is dry-run)")
    parser.add_argument("--no-video", action="store_true", help="Skip the camera stream (window still captures keys)")
    return parser.parse_args()


def handle_key(controller: TelloController, key: int) -> str:
    """Returns exit, override (movement key held), or idle."""
    if key == KEY_SPACE:
        skills.toggle_takeoff_land(controller)
        return "idle"
    return controller.handle_keyboard(key)


def main() -> None:
    args = parse_args()
    print(f"Manual_Mode: {'LIVE' if args.live else 'DRY-RUN'}")

    controller = TelloController(dry_run=not args.live)
    if not controller.connect(with_video=not args.no_video):
        controller.shutdown()
        raise SystemExit(1)

    print_keyboard_help()
    print(" [SPACE] takeoff/land toggle\n")
    try:
        while True:
            key = controller.show_video()
            state = handle_key(controller, key)
            if state == "exit":
                break
            if state != "override":
                controller.apply_motion()
            time.sleep(LOOP_SLEEP_S)
    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        controller.shutdown()


if __name__ == "__main__":
    main()
