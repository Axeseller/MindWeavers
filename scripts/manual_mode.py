from __future__ import annotations

import argparse
import time

import _paths  # noqa: F401
from eeg.detectors import JAW_TAKEOFF_THRESHOLD, jaw_takeoff_config
from eeg.trigger import EegTrigger
from lsl.client import DEFAULT_STREAM_NAME
from mapping.commands import ACTION_SKILLS, KEY_ESC, CommandMapper, key_to_action
from tello.controller import TelloController, print_keyboard_help
from tello.skills import SkillRunner

LOOP_SLEEP_S = 0.01
SHUTDOWN_WAIT_S = 30.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Manual_Mode: jaw clench switches takeoff/land, keyboard drives the basic skills"
    )
    parser.add_argument("--live", action="store_true", help="Connect to the real Tello (default is dry-run)")
    parser.add_argument("--no-video", action="store_true", help="Skip the camera stream (window still captures keys)")
    parser.add_argument("--no-eeg", action="store_true", help="Keyboard only (no headset)")
    parser.add_argument("--stream", default=DEFAULT_STREAM_NAME, help="Unicorn raw LSL stream name")
    parser.add_argument("--threshold", type=float, default=JAW_TAKEOFF_THRESHOLD, help="Jaw RMS enter threshold")
    return parser.parse_args()


def connect_eeg(args: argparse.Namespace) -> EegTrigger | None:
    """Clench trigger with the calibrated takeoff detector, or None to fly keyboard only."""
    if args.no_eeg:
        return None
    trigger = EegTrigger(jaw_takeoff_config(args.threshold))
    if trigger.connect(args.stream):
        return trigger
    if args.live:
        print("No headset stream. Fix Unicorn Recorder or pass --no-eeg to fly keyboard only.")
        raise SystemExit(1)
    print("Continuing in dry-run without EEG (keyboard only).")
    return None


def handle_eeg(trigger: EegTrigger, mapper: CommandMapper, runner: SkillRunner) -> None:
    now = time.monotonic()
    for event in trigger.poll(now):
        print(f"EEG event: {event}  jaw_rms={trigger.jaw_rms:.1f}")
        action = mapper.map(event, runner.controller.is_flying, now)
        if action in ACTION_SKILLS:
            runner.request(ACTION_SKILLS[action])


def handle_key(runner: SkillRunner, key: int) -> bool:
    """Returns False when the user asks to exit."""
    if key == KEY_ESC:
        print("\n[!] Exit from keyboard.")
        return False
    action = key_to_action(key, runner.controller.is_flying)
    if action in ACTION_SKILLS:
        runner.request(ACTION_SKILLS[action])
    return True


def main() -> None:
    args = parse_args()
    print(f"Manual_Mode: {'LIVE' if args.live else 'DRY-RUN'}")

    controller = TelloController(dry_run=not args.live)
    if not controller.connect(with_video=not args.no_video):
        controller.shutdown()
        raise SystemExit(1)
    try:
        trigger = connect_eeg(args)
    except SystemExit:
        controller.shutdown()
        raise

    runner = SkillRunner(controller)
    mapper = CommandMapper(cooldown_s=1.0)
    print_keyboard_help()
    if trigger is not None:
        print("Clench your jaw ~0.5-1 s to switch takeoff/land.\n")
    try:
        running = True
        while running:
            if trigger is not None:
                handle_eeg(trigger, mapper, runner)
            running = handle_key(runner, controller.show_video())
            runner.tick()
            time.sleep(LOOP_SLEEP_S)
    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        if trigger is not None:
            trigger.close()
        runner.wait_idle(SHUTDOWN_WAIT_S)
        controller.shutdown()


if __name__ == "__main__":
    main()
