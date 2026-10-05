from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from eeg.detectors import jaw_takeoff_config  # noqa: E402
from eeg.preprocess import SAMPLE_RATE  # noqa: E402
from eeg.trigger import EegTrigger  # noqa: E402
from lsl.client import EEG_CHANNEL_COUNT, TOTAL_CHANNEL_COUNT, LslClient  # noqa: E402
from mapping.commands import Event  # noqa: E402

CHUNK = 10  # 40 ms of samples per pull
DC_OFFSET_UV = 3000.0
REST_UV = 8.0
CLENCH_UV = 180.0


def synthetic_eeg(seconds: float, clench: tuple[float, float] | None = None) -> np.ndarray:
    """Raw Unicorn-like scans: DC offset + rest noise, plus broadband EMG during (start_s, duration_s)."""
    rng = np.random.default_rng(0)
    n = int(seconds * SAMPLE_RATE)
    data = np.zeros((n, TOTAL_CHANNEL_COUNT))
    data[:, :EEG_CHANNEL_COUNT] = DC_OFFSET_UV + rng.normal(0, REST_UV, (n, EEG_CHANNEL_COUNT))
    if clench:
        start, end = int(clench[0] * SAMPLE_RATE), int(sum(clench) * SAMPLE_RATE)
        data[start:end, :EEG_CHANNEL_COUNT] += rng.normal(0, CLENCH_UV, (end - start, EEG_CHANNEL_COUNT))
    return data


class FakeInlet:
    """Serves recorded samples in fixed chunks, like pylsl.StreamInlet.pull_chunk."""

    def __init__(self, data: np.ndarray) -> None:
        self.data = data
        self.pos = 0

    def pull_chunk(self, timeout: float = 0.0, max_samples: int = 64) -> tuple[list, list]:
        end = min(self.pos + min(CHUNK, max_samples), len(self.data))
        rows = self.data[self.pos : end].tolist()
        self.pos = end
        return rows, [0.0] * len(rows)


def replay(data: np.ndarray) -> tuple[list[str], EegTrigger]:
    client = LslClient()
    inlet = FakeInlet(data)
    client._inlet = inlet
    client._channel_count = data.shape[1]
    trigger = EegTrigger(jaw_takeoff_config(), client)
    events: list[str] = []
    while inlet.pos < len(data):
        events.extend(trigger.poll(now=(inlet.pos + CHUNK) / SAMPLE_RATE))
    return events, trigger


class EegTriggerTest(unittest.TestCase):
    def test_short_clench_fires_one_switch_event(self) -> None:
        events, _trigger = replay(synthetic_eeg(6.0, clench=(2.0, 0.8)))
        self.assertEqual(events, [Event.JAW_SHORT])

    def test_rest_never_fires(self) -> None:
        events, _trigger = replay(synthetic_eeg(10.0))
        self.assertEqual(events, [])

    def test_long_clench_is_not_a_switch(self) -> None:
        events, _trigger = replay(synthetic_eeg(8.0, clench=(2.0, 3.0)))
        self.assertIn(Event.JAW_LONG, events)
        self.assertNotIn(Event.JAW_SHORT, events)

    def test_waits_for_a_full_window(self) -> None:
        events, trigger = replay(synthetic_eeg(0.96, clench=(0.0, 0.96)))
        self.assertEqual(events, [])
        self.assertEqual(trigger.jaw_rms, 0.0)


if __name__ == "__main__":
    unittest.main()
