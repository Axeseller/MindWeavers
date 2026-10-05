from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "artifacts"))

import vuelo  # noqa: E402
import vuelo5  # noqa: E402


class RecordingTello(vuelo.DryRunTello):
    def __init__(self) -> None:
        self.calls: list = []

    def takeoff(self) -> None:
        self.calls.append("takeoff")

    def land(self) -> None:
        self.calls.append("land")

    def send_rc_control(self, lr: int, fb: int, ud: int, yv: int) -> None:
        self.calls.append((lr, fb, ud, yv))


class FlightKeysTest(unittest.TestCase):
    def fly(self, keys, names):
        tello = RecordingTello()
        flight = vuelo.Flight(tello, keys)
        flight.gesture("jaw", 0.0)
        results = []
        for i, name in enumerate(names):
            flight.gesture(name, 10.0 * (i + 1))
            flight.tick(10.0 * (i + 1) + 0.05)
            results.append(tello.calls[-1])
        return tello, flight, results

    def test_three_input_flight_is_unchanged(self) -> None:
        self.assertEqual(vuelo.INPUTS, ("jaw", "cuello", "blink"))
        _tello, _flight, results = self.fly(vuelo.KEYS, ["cuello", "blink"])
        self.assertEqual(results, [(0, 50, 0, 0), (0, -50, 0, 0)])

    def test_five_input_flight_adds_left_and_right(self) -> None:
        self.assertEqual(vuelo5.INPUTS, ("jaw", "cuello", "blink", "angry", "happy"))
        _tello, _flight, results = self.fly(vuelo5.KEYS, ["cuello", "blink", "happy", "angry"])
        self.assertEqual(results, [(0, 50, 0, 0), (0, -50, 0, 0), (50, 0, 0, 0), (-50, 0, 0, 0)])

    def test_nothing_moves_while_grounded(self) -> None:
        tello = RecordingTello()
        flight = vuelo.Flight(tello, vuelo5.KEYS)
        for name in ("happy", "angry", "cuello", "blink"):
            self.assertIn("ignored", flight.gesture(name, 0.0))
        self.assertEqual(tello.calls, [])

    def test_jaw_takes_off_then_lands(self) -> None:
        tello, flight, _ = self.fly(vuelo5.KEYS, [])
        self.assertTrue(flight.is_flying)
        flight.gesture("jaw", 5.0)
        self.assertFalse(flight.is_flying)
        self.assertEqual([c for c in tello.calls if isinstance(c, str)], ["takeoff", "land"])

    def test_movement_returns_to_hover(self) -> None:
        tello, flight, _ = self.fly(vuelo5.KEYS, ["happy"])
        flight.tick(20.0)
        self.assertEqual(tello.calls[-1], (0, 0, 0, 0))


if __name__ == "__main__":
    unittest.main()
