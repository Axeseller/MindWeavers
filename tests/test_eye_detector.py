from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from eeg.detectors import ArtifactDetector, camera_blink_config  # noqa: E402
from mapping.commands import Event  # noqa: E402

STEP_S = 0.05
BLINK_HIGH = 80.0
CLOSED_HIGH = 10.0
LOW = 1.0


def run(blinks: list[tuple[float, float]], closed: list[tuple[float, float]] | None = None) -> list[str]:
    """Feed (value, seconds) segments. `closed` defaults to LOW for the same timeline."""
    detector = ArtifactDetector(camera_blink_config())
    events: list[str] = []
    t = 0.0
    closed = closed or [(LOW, sum(seconds for _value, seconds in blinks))]
    blink_stream = _expand(blinks)
    closed_stream = _expand(closed)
    for blink_amp, eyes_amp in zip(blink_stream, closed_stream):
        events.extend(detector.update(0.0, blink_amp, t, eyes_amp))
        t += STEP_S
    return events


def _expand(sequence: list[tuple[float, float]]) -> list[float]:
    values: list[float] = []
    for value, seconds in sequence:
        values.extend([value] * round(seconds / STEP_S))
    return values


class CameraBlinkDetectorTest(unittest.TestCase):
    def test_rest_never_triggers(self) -> None:
        self.assertEqual(run([(LOW, 10.0)]), [])

    def test_single_blink_takes_a_photo_event(self) -> None:
        self.assertEqual(run([(LOW, 1.0), (BLINK_HIGH, 0.3), (LOW, 1.0)]), [Event.BLINK])

    def test_jaw_is_disabled(self) -> None:
        detector = ArtifactDetector(camera_blink_config())
        events = []
        t = 0.0
        for _ in range(40):
            events.extend(detector.update(80.0, LOW, t, LOW))
            t += STEP_S
        self.assertEqual(events, [])

    def test_eyes_closed_hold_starts_then_open_stops(self) -> None:
        events = run(
            [(LOW, 6.0)],
            [(LOW, 1.0), (CLOSED_HIGH, 3.0), (LOW, 1.0)],
        )
        self.assertEqual(events, [Event.EYES_CLOSED, Event.EYES_OPENED])

    def test_brief_alpha_spike_is_ignored(self) -> None:
        events = run(
            [(LOW, 3.0)],
            [(LOW, 1.0), (CLOSED_HIGH, 0.8), (LOW, 1.0)],
        )
        self.assertEqual(events, [])

    def test_blink_ignored_while_eyes_are_closed(self) -> None:
        events = run(
            [(LOW, 1.0), (BLINK_HIGH, 2.5), (LOW, 1.0)],
            [(LOW, 1.0), (CLOSED_HIGH, 3.0), (LOW, 0.5)],
        )
        self.assertEqual(events, [Event.EYES_CLOSED, Event.EYES_OPENED])


if __name__ == "__main__":
    unittest.main()
