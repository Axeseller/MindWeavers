from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import app  # noqa: E402
from mapping.commands import Action, CommandMapper, Event, key_to_action  # noqa: E402
from tello.controller import RC_SPEED, TelloController  # noqa: E402
from tello.skills import skill_rc  # noqa: E402


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

    def test_other_events_unchanged_and_ignore_cooldown(self) -> None:
        mapper = CommandMapper(cooldown_s=1.0)
        mapper.map(Event.JAW_SHORT, False, 0.0)
        self.assertEqual(mapper.map(Event.JAW_LONG, True, 0.1), Action.LAND)
        self.assertEqual(mapper.map(Event.JAW_EMERGENCY, True, 0.1), Action.EMERGENCY)
        self.assertEqual(mapper.map(Event.DOUBLE_BLINK, True, 0.1), Action.PHOTO)

    def test_rotation_events_map_to_yaw_actions(self) -> None:
        mapper = CommandMapper(cooldown_s=1.0)
        mapper.map(Event.JAW_SHORT, False, 0.0)
        self.assertEqual(mapper.map(Event.ROTATE_CW, True, 0.1), Action.YAW_CW)
        self.assertEqual(mapper.map(Event.ROTATE_CCW, True, 0.1), Action.YAW_CCW)

    def test_new_artifact_events_are_not_mapped_yet(self) -> None:
        mapper = CommandMapper()
        self.assertIsNone(mapper.map(Event.BLINK, True, 0.0))
        self.assertIsNone(mapper.map(Event.PUNO_IZQ, True, 0.0))
        self.assertIsNone(mapper.map(Event.CUELLO_DER, False, 0.0))

    def test_key_to_action_space_toggles(self) -> None:
        self.assertEqual(key_to_action(32, False), Action.TAKEOFF)
        self.assertEqual(key_to_action(32, True), Action.LAND)
        self.assertEqual(key_to_action(ord("t"), True), Action.YAW_CW)

    def test_rotation_event_reaches_yaw_skill(self) -> None:
        controller = TelloController(dry_run=True)
        controller.takeoff()
        action = CommandMapper().map(Event.ROTATE_CCW, controller.is_flying, 0.0)
        app.apply_action(controller, action)
        self.assertEqual(controller.burst_rc, (0, 0, 0, -RC_SPEED))


class ApplyActionTest(unittest.TestCase):
    def test_every_movement_action_starts_its_skill(self) -> None:
        for action, skill in app.ACTION_SKILLS.items():
            with self.subTest(action=action):
                controller = TelloController(dry_run=True)
                controller.takeoff()
                app.apply_action(controller, action)
                self.assertEqual(controller.burst_rc, skill_rc(skill))

    def test_yaw_actions_rotate_in_their_direction(self) -> None:
        for action, yaw_sign in ((Action.YAW_CW, 1), (Action.YAW_CCW, -1)):
            with self.subTest(action=action):
                controller = TelloController(dry_run=True)
                controller.takeoff()
                app.apply_action(controller, action)
                lr, fb, ud, yv = controller.burst_rc
                self.assertEqual((lr, fb, ud), (0, 0, 0))
                self.assertEqual(yv, yaw_sign * RC_SPEED)

    def test_yaw_actions_ignored_while_grounded(self) -> None:
        for action in (Action.YAW_CW, Action.YAW_CCW):
            with self.subTest(action=action):
                controller = TelloController(dry_run=True)
                app.apply_action(controller, action)
                self.assertFalse(controller.burst_active)

    def test_takeoff_and_land_actions(self) -> None:
        controller = TelloController(dry_run=True)
        app.apply_action(controller, Action.TAKEOFF)
        self.assertTrue(controller.is_flying)
        app.apply_action(controller, Action.LAND)
        self.assertFalse(controller.is_flying)


if __name__ == "__main__":
    unittest.main()
