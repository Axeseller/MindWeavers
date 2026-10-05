from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import app  # noqa: E402
from mapping.commands import Action, CommandMapper, Event  # noqa: E402
from tello.controller import TelloController  # noqa: E402
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


class ApplyActionTest(unittest.TestCase):
    def test_every_movement_action_starts_its_skill(self) -> None:
        for action, skill in app.ACTION_SKILLS.items():
            with self.subTest(action=action):
                controller = TelloController(dry_run=True)
                controller.takeoff()
                app.apply_action(controller, action)
                self.assertEqual(controller.burst_rc, skill_rc(skill))

    def test_takeoff_and_land_actions(self) -> None:
        controller = TelloController(dry_run=True)
        app.apply_action(controller, Action.TAKEOFF)
        self.assertTrue(controller.is_flying)
        app.apply_action(controller, Action.LAND)
        self.assertFalse(controller.is_flying)


if __name__ == "__main__":
    unittest.main()
