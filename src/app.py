from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

SRC = Path(__file__).resolve().parent
ROOT = SRC.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from eeg.detectors import ArtifactDetector
from eeg.preprocess import extract_features, preprocess_window
from lsl.client import DEFAULT_STREAM_NAME, LslClient
from mapping.commands import Action, CommandMapper
from tello import skills
from tello.controller import TelloController, print_keyboard_help

PHOTO_DIR = ROOT / "data" / "recordings"
LOOP_SLEEP_S = 0.01

ACTION_SKILLS = {
    Action.FORWARD: "forward",
    Action.BACK: "back",
    Action.LEFT: "left",
    Action.RIGHT: "right",
    Action.UP: "up",
    Action.DOWN: "down",
    Action.YAW_CW: "yaw_clockwise",
    Action.YAW_CCW: "yaw_counterclockwise",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Unicorn raw LSL → Tello commands")
    parser.add_argument("--dry-run", action="store_true", help="Print commands, do not connect to Tello")
    parser.add_argument("--no-video", action="store_true", help="Skip Tello camera stream")
    parser.add_argument("--no-lsl", action="store_true", help="Keyboard only (no headset)")
    parser.add_argument("--stream", default=DEFAULT_STREAM_NAME, help="Unicorn raw LSL stream name")
    return parser.parse_args()


def apply_action(controller: TelloController, action: str) -> None:
    if action == Action.TAKEOFF:
        controller.takeoff()
    elif action == Action.LAND:
        controller.land()
    elif action == Action.EMERGENCY:
        controller.emergency_land()
    elif action in ACTION_SKILLS:
        skills.start_skill(controller, ACTION_SKILLS[action])
    elif action == Action.PHOTO:
        controller.take_photo(PHOTO_DIR)


def process_eeg(client: LslClient, detector: ArtifactDetector, mapper: CommandMapper, flying: bool) -> list[str]:
    client.pull_chunk(timeout=0.0)
    window = preprocess_window(client.window())
    jaw_rms, blink_amp = extract_features(window)
    now = time.monotonic()
    events = detector.update(jaw_rms, blink_amp, now)
    actions: list[str] = []
    for event in events:
        print(f"EEG event: {event}  jaw_rms={jaw_rms:.1f}  blink={blink_amp:.1f}")
        action = mapper.map(event, flying, now)
        if action:
            actions.append(action)
    return actions


def run(args: argparse.Namespace) -> None:
    controller = TelloController(dry_run=args.dry_run)
    client = LslClient()
    detector = ArtifactDetector()
    mapper = CommandMapper(cooldown_s=1.0)
    use_lsl = not args.no_lsl

    if not controller.connect(with_video=not args.no_video):
        return
    if use_lsl and not client.connect(stream_name=args.stream):
        if not args.dry_run:
            controller.shutdown()
            return
        print("Continuing in dry-run without LSL (keyboard only).")
        use_lsl = False

    print_keyboard_help()
    running = True
    try:
        while running:
            if use_lsl:
                for action in process_eeg(client, detector, mapper, controller.is_flying):
                    apply_action(controller, action)
            key = controller.show_video()
            key_state = controller.handle_keyboard(key)
            if key_state == "exit":
                running = False
            elif key_state != "override":
                controller.apply_motion()
            time.sleep(LOOP_SLEEP_S)
    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        client.close()
        controller.shutdown()


if __name__ == "__main__":
    run(parse_args())
