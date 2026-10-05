from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from eeg.detectors import HoldDetector, artifact_spec  # noqa: E402
from mapping.commands import Event  # noqa: E402

STEP_S = 0.05
HIGH = 20.0
LOW = 1.0


def run(spec_name: str, sequence: list[tuple[float, float]], threshold: float = 10.0) -> list[str]:
    detector = HoldDetector(artifact_spec(spec_name, threshold))
    events: list[str] = []
    t = 0.0
    for value, seconds in sequence:
        for _ in range(round(seconds / STEP_S)):
            event = detector.update(value, t)
            if event:
                events.append(event)
            t += STEP_S
    return events


class HoldDetectorTest(unittest.TestCase):
    def test_rest_never_triggers_neck(self) -> None:
        self.assertEqual(run("cuello_izq", [(LOW, 8.0)]), [])

    def test_release_hold_emits_once(self) -> None:
        self.assertEqual(run("cuello_izq", [(LOW, 1.0), (HIGH, 1.0), (LOW, 1.0)]), [Event.CUELLO_IZQ])

    def test_brief_spike_is_ignored(self) -> None:
        self.assertEqual(run("cuello_izq", [(LOW, 1.0), (HIGH, 0.1), (LOW, 1.0)]), [])

    def test_enter_emits_on_rising_edge(self) -> None:
        self.assertEqual(run("blink", [(LOW, 1.0), (HIGH, 0.3), (LOW, 1.0)]), [Event.BLINK])

    def test_hold_emits_after_min_duration(self) -> None:
        events = run("cerrar_ojos", [(LOW, 1.0), (HIGH, 2.5), (LOW, 1.0)])
        self.assertEqual(events, [Event.EYES_CLOSED])

    def test_unknown_artifact_raises(self) -> None:
        with self.assertRaises(KeyError):
            artifact_spec("not_a_gesture")


if __name__ == "__main__":
    unittest.main()
