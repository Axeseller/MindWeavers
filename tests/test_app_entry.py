from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import app  # noqa: E402


class AppEntryTest(unittest.TestCase):
    def test_app_runs_the_simple_flight(self) -> None:
        self.assertEqual(app.FLIGHT.name, "vuelo.py")
        self.assertTrue(app.FLIGHT.exists())

    def test_lados_selects_the_five_input_flight(self) -> None:
        self.assertEqual(app.FLIGHT_SIDES.name, "vuelo5.py")
        self.assertTrue(app.FLIGHT_SIDES.exists())
        self.assertEqual(app.translate_legacy_args(["--lados", "--dry-run"]), ["--dry-run"])

    def test_dry_run_and_replay_pass_through(self) -> None:
        self.assertEqual(app.translate_legacy_args(["--dry-run", "--replay", "x.csv"]), ["--dry-run", "--replay", "x.csv"])

    def test_old_flags(self) -> None:
        self.assertEqual(app.translate_legacy_args(["--no-video"]), [])
        self.assertEqual(app.translate_legacy_args(["--threshold", "30"]), ["--threshold", "jaw=30"])
        self.assertEqual(app.translate_legacy_args(["--threshold=30"]), ["--threshold", "jaw=30"])
        with self.assertRaises(SystemExit):
            app.translate_legacy_args(["--no-lsl"])


if __name__ == "__main__":
    unittest.main()
