from __future__ import annotations

import sys
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tello import skills  # noqa: E402
from tello.controller import RC_SPEED, TelloController  # noqa: E402
from tello.skills import SkillKind, SkillRunner  # noqa: E402

HOVER = ("rc", 0, 0, 0, 0)


class FakeTello:
    """Records SDK calls so tests can check what would reach the drone."""

    def __init__(self, block_takeoff: bool = False, fail_land: bool = False) -> None:
        self.calls: list[tuple] = []
        self.takeoff_gate = threading.Event()
        if not block_takeoff:
            self.takeoff_gate.set()
        self.fail_land = fail_land

    def takeoff(self) -> None:
        self.takeoff_gate.wait(5)
        self.calls.append(("takeoff",))

    def land(self) -> None:
        self.calls.append(("land",))
        if self.fail_land:
            raise RuntimeError("Command 'land' was unsuccessful")

    def send_rc_control(self, lr: int, fb: int, ud: int, yv: int) -> None:
        self.calls.append(("rc", lr, fb, ud, yv))


def make_runner(flying: bool = True, **fake_options) -> tuple[SkillRunner, TelloController, FakeTello]:
    controller = TelloController(dry_run=False)
    fake = FakeTello(**fake_options)
    controller._tello = fake
    if flying:
        controller.takeoff()
    return SkillRunner(controller), controller, fake


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


class RegistryTest(unittest.TestCase):
    def test_skill_kinds(self) -> None:
        self.assertEqual(skills.skill_kind("takeoff"), SkillKind.PROCESS)
        self.assertEqual(skills.skill_kind("land"), SkillKind.PROCESS)
        for name in EXPECTED_RC:
            self.assertEqual(skills.skill_kind(name), SkillKind.CONTINUOUS)

    def test_invalid_arguments_raise(self) -> None:
        runner, _controller, _fake = make_runner()
        with self.assertRaises(ValueError):
            runner.request("sideways")
        with self.assertRaises(ValueError):
            runner.request("forward", speed=150)
        with self.assertRaises(ValueError):
            runner.request("forward", lease_s=0)


class ContinuousSkillTest(unittest.TestCase):
    def test_every_movement_sends_its_rc_tuple(self) -> None:
        for name, rc in EXPECTED_RC.items():
            with self.subTest(skill=name):
                runner, controller, fake = make_runner()
                self.assertTrue(runner.request(name))
                self.assertEqual(fake.calls[-1], ("rc", *rc))
                self.assertEqual(controller.burst_rc, rc)

    def test_speed_scales_direction(self) -> None:
        runner, _controller, fake = make_runner()
        runner.request("back", speed=20)
        self.assertEqual(fake.calls[-1], ("rc", 0, -20, 0, 0))

    def test_grounded_movement_is_ignored(self) -> None:
        runner, _controller, fake = make_runner(flying=False)
        self.assertFalse(runner.request("up"))
        runner.tick()
        self.assertEqual(fake.calls, [])

    def test_moves_while_requested_then_hovers(self) -> None:
        runner, controller, fake = make_runner()
        runner.request("forward", lease_s=0.3)
        time.sleep(0.2)
        runner.request("forward", lease_s=0.3)  # action persists: lease extends
        time.sleep(0.2)
        runner.tick()
        self.assertTrue(controller.burst_active)
        self.assertEqual(fake.calls[-1], ("rc", 0, RC_SPEED, 0, 0))
        time.sleep(0.25)  # requests stopped: lease runs out
        runner.tick()
        self.assertFalse(controller.burst_active)
        self.assertEqual(fake.calls[-1], HOVER)

    def test_release_stops_now(self) -> None:
        runner, controller, fake = make_runner()
        runner.request("left", lease_s=5.0)
        runner.release()
        runner.tick()
        self.assertFalse(controller.burst_active)
        self.assertEqual(fake.calls[-1], HOVER)

    def test_land_cancels_motion(self) -> None:
        runner, controller, fake = make_runner()
        runner.request("forward", lease_s=5.0)
        self.assertTrue(runner.request("land"))
        self.assertTrue(runner.wait_idle(2))
        self.assertFalse(controller.burst_active)
        self.assertFalse(controller.is_flying)
        self.assertEqual(fake.calls[-2:], [HOVER, ("land",)])


class ProcessSkillTest(unittest.TestCase):
    def test_process_rejects_everything_until_done(self) -> None:
        runner, controller, fake = make_runner(flying=False, block_takeoff=True)
        self.assertTrue(runner.request("takeoff"))
        self.assertTrue(runner.busy)
        self.assertFalse(runner.request("land"))
        self.assertFalse(runner.request("takeoff"))
        self.assertFalse(runner.request("forward"))
        self.assertIsNone(runner.toggle_takeoff_land())
        runner.tick()
        self.assertEqual(fake.calls, [])  # no RC while the process runs

        fake.takeoff_gate.set()
        self.assertTrue(runner.wait_idle(2))
        self.assertFalse(runner.busy)
        self.assertTrue(controller.is_flying)
        self.assertEqual(fake.calls, [("takeoff",)])
        self.assertTrue(runner.request("forward"))  # accepts input again

    def test_sdk_failure_does_not_raise(self) -> None:
        runner, controller, _fake = make_runner(fail_land=True)
        self.assertTrue(runner.request("land"))
        self.assertTrue(runner.wait_idle(2))
        self.assertFalse(runner.busy)
        self.assertTrue(controller.is_flying)  # land failed, state unchanged
        self.assertTrue(runner.request("land"))  # runner still usable
        runner.wait_idle(2)

    def test_toggle_takes_off_then_lands(self) -> None:
        runner, controller, fake = make_runner(flying=False)
        self.assertEqual(runner.toggle_takeoff_land(), "takeoff")
        runner.wait_idle(2)
        self.assertTrue(controller.is_flying)
        self.assertEqual(runner.toggle_takeoff_land(), "land")
        runner.wait_idle(2)
        self.assertFalse(controller.is_flying)
        self.assertEqual([c[0] for c in fake.calls], ["takeoff", "rc", "land"])

    def test_dry_run_simulates_process_time(self) -> None:
        controller = TelloController(dry_run=True)
        runner = SkillRunner(controller, dry_run_process_s=0.2)
        self.assertTrue(runner.request("takeoff"))
        self.assertTrue(runner.busy)
        self.assertFalse(runner.request("forward"))
        self.assertTrue(runner.wait_idle(2))
        self.assertTrue(controller.is_flying)
        self.assertTrue(runner.request("forward"))


if __name__ == "__main__":
    unittest.main()
