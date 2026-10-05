from __future__ import annotations

import argparse
import sys
import time
from dataclasses import replace
from pathlib import Path

SRC = Path(__file__).resolve().parent
ROOT = SRC.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from eeg.detectors import JAW_TAKEOFF_THRESHOLD, DetectorConfig, jaw_takeoff_config
from eeg.trigger import EegTrigger
from lsl.client import DEFAULT_STREAM_NAME
from mapping.commands import ACTION_SKILLS, KEY_ESC, Action, CommandMapper, key_to_action
from tello.controller import TelloController, print_keyboard_help
from tello.skills import SkillRunner

PHOTO_DIR = ROOT / "data" / "recordings"
LOOP_SLEEP_S = 0.01
SHUTDOWN_WAIT_S = 30.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Unicorn raw LSL → Tello commands")
    parser.add_argument("--dry-run", action="store_true", help="Print commands, do not connect to Tello")
    parser.add_argument("--no-video", action="store_true", help="Skip Tello camera stream")
    parser.add_argument("--no-lsl", action="store_true", help="Keyboard only (no headset)")
    parser.add_argument("--stream", default=DEFAULT_STREAM_NAME, help="Unicorn raw LSL stream name")
    parser.add_argument("--threshold", type=float, default=JAW_TAKEOFF_THRESHOLD, help="Jaw RMS enter threshold")
    return parser.parse_args()


def detector_config(threshold: float) -> DetectorConfig:
    """Calibrated jaw timing from jaw_takeoff_config, with the double-blink photo kept on."""
    return replace(jaw_takeoff_config(threshold), blink_peak_threshold=DetectorConfig.blink_peak_threshold)


def apply_action(runner: SkillRunner, action: str) -> None:
    if action == Action.PHOTO:
        runner.controller.take_photo(PHOTO_DIR)
    elif action in ACTION_SKILLS:
        runner.request(ACTION_SKILLS[action])


def process_eeg(trigger: EegTrigger, mapper: CommandMapper, flying: bool) -> list[str]:
    now = time.monotonic()
    actions: list[str] = []
    for event in trigger.poll(now):
        print(f"EEG event: {event}  jaw_rms={trigger.jaw_rms:.1f}  blink={trigger.blink_amp:.1f}")
        action = mapper.map(event, flying, now)
        if action:
            actions.append(action)
    return actions


def run(args: argparse.Namespace) -> None:
    controller = TelloController(dry_run=args.dry_run)
    runner = SkillRunner(controller)
    trigger = EegTrigger(detector_config(args.threshold))
    mapper = CommandMapper(cooldown_s=1.0)
    use_lsl = not args.no_lsl

    if not controller.connect(with_video=not args.no_video):
        controller.shutdown()
        return
    if use_lsl and not trigger.connect(args.stream):
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
                for action in process_eeg(trigger, mapper, controller.is_flying):
                    apply_action(runner, action)
            key = controller.show_video()
            if key == KEY_ESC:
                print("\n[!] Exit from keyboard.")
                running = False
            else:
                action = key_to_action(key, controller.is_flying)
                if action:
                    apply_action(runner, action)
            runner.tick()
            time.sleep(LOOP_SLEEP_S)
    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        trigger.close()
        runner.wait_idle(SHUTDOWN_WAIT_S)
        controller.shutdown()


if __name__ == "__main__":
    run(parse_args())
