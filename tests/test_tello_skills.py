from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tello import skills  # noqa: E402
from tello.controller import RC_SPEED, TelloController  # noqa: E402


class FakeTello:
    """Records SDK calls so tests can check what would reach the drone."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def takeoff(self) -> None:
        self.calls.append(("takeoff",))

    def land(self) -> None:
        self.calls.append(("land",))

    def emergency(self) -> None:
        self.calls.append(("emergency",))

    def send_rc_control(self, lr: int, fb: int, ud: int, yv: int) -> None:
        self.calls.append(("rc", lr, fb, ud, yv))


def make_controller(flying: bool = True) -> tuple[TelloController, FakeTello]:
    controller = TelloController(dry_run=False)
    fake = FakeTello()
    controller._tello = fake
    if flying:
        controller.takeoff()
    return controller, fake


EXPECTED_RC = {
    "forward": (0, RC_SPEED, 0, 0),
    "back": (0, -RC_SPEED, 0, 0),
    "right": (RC_SPEED, 0, 0, 0),
    "left": (-RC_SPEED, 0, 0, 0),
    "up": (0, 0, RC_SPEED, 0),
    "down": (0, 0, -RC_SPEED, 0),
    "yaw_clockwise": (0, 0, 0, RC_SPEED),
    "yaw_counterclockwise": (0, 0, 0, -RC_SPEED),
}


class MovementSkillTest(unittest.TestCase):
    def test_every_named_skill_sends_its_rc_tuple(self) -> None:
        for name, rc in EXPECTED_RC.items():
            with self.subTest(skill=name):
                controller, fake = make_controller()
                self.assertTrue(getattr(skills, name)(controller, seconds=1.0))
                self.assertEqual(fake.calls[-1], ("rc", *rc))
                self.assertEqual(controller.burst_rc, rc)

    def test_speed_scales_direction(self) -> None:
        controller, fake = make_controller()
        skills.back(controller, seconds=1.0, speed=20)
        self.assertEqual(fake.calls[-1], ("rc", 0, -20, 0, 0))

    def test_grounded_skill_is_ignored(self) -> None:
        controller, fake = make_controller(flying=False)
        self.assertFalse(skills.up(controller))
        self.assertEqual(fake.calls, [])

    def test_burst_expires_into_hover(self) -> None:
        controller, fake = make_controller()
        self.assertTrue(skills.run_skill(controller, "left", seconds=0.1))
        self.assertFalse(controller.burst_active)
        self.assertEqual(fake.calls[-1], ("rc", 0, 0, 0, 0))
        self.assertIn(("rc", -RC_SPEED, 0, 0, 0), fake.calls)

    def test_land_cancels_active_burst(self) -> None:
        controller, fake = make_controller()
        skills.forward(controller, seconds=5.0)
        controller.land()
        self.assertFalse(controller.burst_active)
        self.assertEqual(fake.calls[-2:], [("rc", 0, 0, 0, 0), ("land",)])

    def test_invalid_arguments_raise(self) -> None:
        controller, _fake = make_controller()
        with self.assertRaises(ValueError):
            skills.start_skill(controller, "sideways")
        with self.assertRaises(ValueError):
            skills.forward(controller, seconds=0)
        with self.assertRaises(ValueError):
            skills.forward(controller, speed=150)


class RotationSkillTest(unittest.TestCase):
    def test_speed_scales_yaw_sign(self) -> None:
        controller, fake = make_controller()
        skills.yaw_clockwise(controller, seconds=1.0, speed=30)
        self.assertEqual(fake.calls[-1], ("rc", 0, 0, 0, 30))
        skills.yaw_counterclockwise(controller, seconds=1.0, speed=30)
        self.assertEqual(fake.calls[-1], ("rc", 0, 0, 0, -30))

    def test_grounded_rotation_is_ignored(self) -> None:
        for name in ("yaw_clockwise", "yaw_counterclockwise"):
            with self.subTest(skill=name):
                controller, fake = make_controller(flying=False)
                self.assertFalse(getattr(skills, name)(controller))
                self.assertEqual(fake.calls, [])

    def test_rotation_expires_into_hover(self) -> None:
        for name, rc in (("yaw_clockwise", (0, 0, 0, RC_SPEED)), ("yaw_counterclockwise", (0, 0, 0, -RC_SPEED))):
            with self.subTest(skill=name):
                controller, fake = make_controller()
                self.assertTrue(skills.run_skill(controller, name, seconds=0.1))
                self.assertFalse(controller.burst_active)
                self.assertIn(("rc", *rc), fake.calls)
                self.assertEqual(fake.calls[-1], ("rc", 0, 0, 0, 0))

    def test_land_and_emergency_cancel_rotation(self) -> None:
        controller, fake = make_controller()
        skills.yaw_clockwise(controller, seconds=5.0)
        controller.land()
        self.assertFalse(controller.burst_active)
        self.assertEqual(fake.calls[-2:], [("rc", 0, 0, 0, 0), ("land",)])

        controller, fake = make_controller()
        skills.yaw_counterclockwise(controller, seconds=5.0)
        controller.emergency_land()
        self.assertFalse(controller.burst_active)
        self.assertEqual(fake.calls[-2:], [("rc", 0, 0, 0, 0), ("emergency",)])

    def test_keyboard_rotation_only_after_takeoff(self) -> None:
        controller, fake = make_controller(flying=False)
        self.assertEqual(controller.handle_keyboard(ord("t")), "override")
        self.assertEqual(fake.calls, [])

        controller.takeoff()
        self.assertEqual(controller.handle_keyboard(ord("t")), "override")
        self.assertEqual(fake.calls[-1], ("rc", 0, 0, 0, RC_SPEED))
        self.assertEqual(controller.handle_keyboard(ord("r")), "override")
        self.assertEqual(fake.calls[-1], ("rc", 0, 0, 0, -RC_SPEED))

        controller.apply_motion()
        self.assertEqual(fake.calls[-1], ("rc", 0, 0, 0, 0))


class ToggleTakeoffLandTest(unittest.TestCase):
    def test_toggle_takes_off_then_lands(self) -> None:
        controller, fake = make_controller(flying=False)
        self.assertEqual(skills.toggle_takeoff_land(controller), "TAKEOFF")
        self.assertTrue(controller.is_flying)
        self.assertEqual(skills.toggle_takeoff_land(controller), "LAND")
        self.assertFalse(controller.is_flying)
        self.assertEqual([c[0] for c in fake.calls], ["takeoff", "rc", "land"])

    def test_toggle_in_dry_run(self) -> None:
        controller = TelloController(dry_run=True)
        self.assertEqual(skills.toggle_takeoff_land(controller), "TAKEOFF")
        self.assertEqual(skills.toggle_takeoff_land(controller), "LAND")


class CameraControllerTest(unittest.TestCase):
    def test_dry_run_photo_and_video(self) -> None:
        controller = TelloController(dry_run=True)
        controller.connect(with_video=False)
        self.assertFalse(controller.camera_on)
        self.assertTrue(controller.start_camera())
        out = Path(tempfile.mkdtemp())
        self.assertIsNotNone(controller.take_photo(out))
        self.assertIsNotNone(controller.start_recording(out))
        self.assertTrue(controller.is_recording)
        controller.record_frame()
        self.assertIsNotNone(controller.stop_recording())
        self.assertFalse(controller.is_recording)
        controller.shutdown()


if __name__ == "__main__":
    unittest.main()
