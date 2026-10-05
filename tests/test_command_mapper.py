from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mapping.commands import ACTION_SKILLS, KEY_NONE, KEY_SPACE, Action, CommandMapper, Event, key_to_action  # noqa: E402
from tello.controller import RC_SPEED, TelloController  # noqa: E402
from tello.skills import SKILLS, SkillRunner, skill_rc  # noqa: E402


def request_action(runner: SkillRunner, action: Action) -> bool:
    """Exercise the action-to-skill table without depending on a retired entry point."""
    return runner.request(ACTION_SKILLS[action])


class CommandMapperTest(unittest.TestCase):
    def test_jaw_short_toggles_on_flight_state(self) -> None:
        mapper = CommandMapper(cooldown_s=1.0)
        self.assertEqual(mapper.map(Event.JAW_SHORT, False, 0.0), Action.TAKEOFF)
        self.assertEqual(mapper.map(Event.JAW_SHORT, True, 2.0), Action.LAND)

    def test_cooldown_blocks_repeat_clench(self) -> None:
        mapper = CommandMapper(cooldown_s=1.0)
        self.assertEqual(mapper.map(Event.JAW_SHORT, False, 0.0), Action.TAKEOFF)
        self.assertIsNone(mapper.map(Event.JAW_SHORT, True, 0.5))
        self.assertEqual(mapper.map(Event.JAW_SHORT, True, 1.0), Action.LAND)

    def test_long_and_emergency_clench_land_and_ignore_cooldown(self) -> None:
        mapper = CommandMapper(cooldown_s=1.0)
        mapper.map(Event.JAW_SHORT, False, 0.0)
        self.assertEqual(mapper.map(Event.JAW_LONG, True, 0.1), Action.LAND)
        self.assertEqual(mapper.map(Event.JAW_EMERGENCY, True, 0.1), Action.LAND)
        self.assertEqual(mapper.map(Event.DOUBLE_BLINK, True, 0.1), Action.PHOTO)

    def test_rotation_events_map_to_yaw_actions(self) -> None:
        mapper = CommandMapper(cooldown_s=1.0)
        mapper.map(Event.JAW_SHORT, False, 0.0)
        self.assertEqual(mapper.map(Event.ROTATE_CW, True, 0.1), Action.YAW_CW)
        self.assertEqual(mapper.map(Event.ROTATE_CCW, True, 0.1), Action.YAW_CCW)

    def test_rotation_event_reaches_yaw_skill(self) -> None:
        controller = TelloController(dry_run=True)
        controller.takeoff()
        action = CommandMapper().map(Event.ROTATE_CCW, controller.is_flying, 0.0)
        request_action(SkillRunner(controller), action)
        self.assertEqual(controller.burst_rc, (0, 0, 0, -RC_SPEED))


class KeyboardTriggerTest(unittest.TestCase):
    def test_layout(self) -> None:
        expected = {
            "q": Action.TAKEOFF,
            "e": Action.LAND,
            "w": Action.FORWARD,
            "s": Action.BACK,
            "a": Action.LEFT,
            "d": Action.RIGHT,
            "y": Action.UP,
            "u": Action.DOWN,
            "r": Action.YAW_CCW,
            "t": Action.YAW_CW,
        }
        for char, action in expected.items():
            with self.subTest(key=char):
                self.assertEqual(key_to_action(ord(char), True), action)
                self.assertEqual(key_to_action(ord(char.upper()), True), action)

    def test_space_switches_on_flight_state(self) -> None:
        self.assertEqual(key_to_action(KEY_SPACE, False), Action.TAKEOFF)
        self.assertEqual(key_to_action(KEY_SPACE, True), Action.LAND)

    def test_unbound_keys(self) -> None:
        self.assertIsNone(key_to_action(KEY_NONE, True))
        self.assertIsNone(key_to_action(ord("x"), True))
        self.assertIsNone(key_to_action(-1, True))


class ActionSkillsTest(unittest.TestCase):
    def test_every_flight_action_has_a_skill(self) -> None:
        self.assertEqual(set(ACTION_SKILLS), set(Action) - {Action.PHOTO})
        for name in ACTION_SKILLS.values():
            self.assertIn(name, SKILLS)


class ApplyActionTest(unittest.TestCase):
    def test_every_movement_action_starts_its_skill(self) -> None:
        for action, skill in ACTION_SKILLS.items():
            if skill in ("takeoff", "land"):
                continue
            with self.subTest(action=action):
                controller = TelloController(dry_run=True)
                controller.takeoff()
                request_action(SkillRunner(controller), action)
                self.assertEqual(controller.burst_rc, skill_rc(skill))

    def test_takeoff_and_land_actions(self) -> None:
        controller = TelloController(dry_run=True)
        runner = SkillRunner(controller, dry_run_process_s=0.0)
        request_action(runner, Action.TAKEOFF)
        runner.wait_idle(2)
        self.assertTrue(controller.is_flying)
        request_action(runner, Action.LAND)
        runner.wait_idle(2)
        self.assertFalse(controller.is_flying)


if __name__ == "__main__":
    unittest.main()
