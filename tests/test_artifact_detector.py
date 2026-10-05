from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from eeg.detectors import ARTIFACT_PARAMS, ArtifactParams, ThresholdDetector  # noqa: E402
from eeg.preprocess import ARTIFACT_CLEANING, SAMPLE_RATE, artifact_feature  # noqa: E402

STEP = 0.04


def feed(detector: ThresholdDetector, values: list[float], start: float = 0.0) -> list[float]:
    """Push one value per 40 ms tick and return the times it fired."""
    return [start + i * STEP for i, v in enumerate(values) if detector.update(v, start + i * STEP)]


class ThresholdDetectorTest(unittest.TestCase):
    def test_pulse_fires_on_release_within_duration(self) -> None:
        detector = ThresholdDetector(ArtifactParams(threshold=10.0, min_s=0.2, max_s=1.0))
        self.assertEqual(len(feed(detector, [0] * 5 + [20] * 10 + [0] * 5)), 1)
        self.assertEqual(detector.peak, 20)

    def test_too_short_and_too_long_are_ignored(self) -> None:
        params = ArtifactParams(threshold=10.0, min_s=0.2, max_s=1.0, refractory_s=0.0)
        self.assertEqual(feed(ThresholdDetector(params), [20] * 2 + [0] * 5), [])
        self.assertEqual(feed(ThresholdDetector(params), [20] * 40 + [0] * 5), [])

    def test_hold_fires_once_while_active(self) -> None:
        detector = ThresholdDetector(ArtifactParams(threshold=5.0, min_s=1.0, hold=True))
        fired = feed(detector, [8] * 100)
        self.assertEqual(len(fired), 1)
        self.assertTrue(detector.active)

    def test_direction_ignores_other_side_and_its_return(self) -> None:
        detector = ThresholdDetector(ArtifactParams(threshold=10.0, direction=+1, refractory_s=1.0))
        # Turn the wrong way, then the return swing (right sign) inside the refractory window.
        self.assertEqual(feed(detector, [-20] * 5 + [0] * 5 + [20] * 5 + [0] * 5), [])
        detector = ThresholdDetector(ArtifactParams(threshold=10.0, direction=+1, refractory_s=1.0))
        self.assertEqual(len(feed(detector, [20] * 5 + [0] * 5 + [-20] * 5 + [0] * 5)), 1)

    def test_refractory_blocks_a_quick_repeat(self) -> None:
        detector = ThresholdDetector(ArtifactParams(threshold=10.0, refractory_s=1.0))
        self.assertEqual(len(feed(detector, ([20] * 3 + [0] * 3) * 3)), 1)


class ArtifactRegistryTest(unittest.TestCase):
    def test_every_artifact_has_cleaning_and_params(self) -> None:
        self.assertEqual(set(ARTIFACT_CLEANING), set(ARTIFACT_PARAMS))
        scripts = Path(__file__).resolve().parents[1] / "scripts" / "artifacts"
        for name in ARTIFACT_PARAMS:
            with self.subTest(artifact=name):
                self.assertTrue((scripts / f"{name}.py").exists())

    def test_rest_noise_stays_below_every_threshold(self) -> None:
        rng = np.random.default_rng(0)
        window = np.zeros((SAMPLE_RATE, 17))
        window[:, :8] = rng.normal(0, 0.5, (SAMPLE_RATE, 8))
        window[:, 11:14] = rng.normal(0, 0.2, (SAMPLE_RATE, 3))
        for name, cleaning in ARTIFACT_CLEANING.items():
            with self.subTest(artifact=name):
                value = artifact_feature(window, cleaning)
                self.assertLess(abs(value), ARTIFACT_PARAMS[name].threshold)


if __name__ == "__main__":
    unittest.main()
