from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from eeg.detectors import ArtifactDetector, jaw_takeoff_config  # noqa: E402
from mapping.commands import Event  # noqa: E402

STEP_S = 0.05
HIGH = 60.0
LOW = 2.0


def run(sequence: list[tuple[float, float]]) -> list[str]:
    """Feed (jaw_rms, seconds) segments into a fresh takeoff detector."""
    detector = ArtifactDetector(jaw_takeoff_config())
    events: list[str] = []
    t = 0.0
    for value, seconds in sequence:
        for _ in range(round(seconds / STEP_S)):
            events.extend(detector.update(value, 0.0, t))
            t += STEP_S
    return events


class JawTakeoffDetectorTest(unittest.TestCase):
    def test_rest_never_triggers(self) -> None:
        self.assertEqual(run([(LOW, 10.0), (30.0, 0.8), (LOW, 2.0)]), [])

    def test_short_clench_triggers_once_on_release(self) -> None:
        self.assertEqual(run([(LOW, 1.0), (HIGH, 0.8), (LOW, 1.0)]), [Event.JAW_SHORT])

    def test_too_brief_spike_is_ignored(self) -> None:
        self.assertEqual(run([(LOW, 1.0), (HIGH, 0.2), (LOW, 1.0)]), [])

    def test_long_clench_is_not_takeoff(self) -> None:
        self.assertNotIn(Event.JAW_SHORT, run([(LOW, 1.0), (HIGH, 3.0), (LOW, 1.0)]))

    def test_hysteresis_keeps_clench_active_between_thresholds(self) -> None:
        events = run([(LOW, 1.0), (HIGH, 0.4), (30.0, 0.4), (LOW, 1.0)])
        self.assertEqual(events, [Event.JAW_SHORT])

    def test_blinks_are_disabled(self) -> None:
        detector = ArtifactDetector(jaw_takeoff_config())
        events = []
        for i in range(40):
            events.extend(detector.update(LOW, 1000.0 if i % 4 == 0 else 0.0, i * STEP_S))
        self.assertEqual(events, [])


if __name__ == "__main__":
    unittest.main()
