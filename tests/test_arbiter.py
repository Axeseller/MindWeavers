from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from eeg import calibration  # noqa: E402
from eeg.arbiter import PRIORITY, InputArbiter  # noqa: E402
from eeg.detectors import ARTIFACT_PARAMS, ArtifactParams, ThresholdDetector  # noqa: E402

STEP = 0.04
PARAMS = {
    "jaw": ArtifactParams(threshold=40.0, min_s=0.2, max_s=2.0, refractory_s=0.2),
    "cerrar_ojos": ArtifactParams(threshold=3.0, min_s=1.0, hold=True, refractory_s=0.2),
    "brazos": ArtifactParams(threshold=10.0, min_s=0.1, direction=-1, refractory_s=0.2),
    "cuello": ArtifactParams(threshold=14.0, min_s=0.1, direction=-1, refractory_s=0.2),
    "blink": ArtifactParams(threshold=30.0, max_s=0.8, refractory_s=0.2),
    "angry": ArtifactParams(threshold=6.0, min_s=0.2, ceiling=25.0, refractory_s=0.2),
    "puno": ArtifactParams(threshold=2.0, min_s=0.1, ceiling=8.0, refractory_s=0.2),
}
QUIET_VALUES = {name: 0.0 for name in PRIORITY}
QUIET_GAUGES = {"motion": 0.5, "pitch": 0.0, "yaw": 0.0, "jaw_emg": 2.0, "frontal_ratio": 1.0}


def play(arbiter: InputArbiter, frames: list[dict[str, float]]) -> list[str]:
    """Feed one frame per 40 ms tick (anything missing is at rest) and return the emitted inputs."""
    out = []
    for i, frame in enumerate(frames):
        values = {**QUIET_VALUES, **{k: v for k, v in frame.items() if k in QUIET_VALUES}}
        gauges = {**QUIET_GAUGES, **{k: v for k, v in frame.items() if k in QUIET_GAUGES}}
        emitted = arbiter.update(values, i * STEP, gauges)
        if emitted:
            out.append(emitted)
    return out


def hold(seconds: float, **frame: float) -> list[dict[str, float]]:
    return [frame] * int(round(seconds / STEP))


class ArbiterTest(unittest.TestCase):
    def setUp(self) -> None:
        self.arbiter = InputArbiter(params=PARAMS)

    def test_priority_order(self) -> None:
        self.assertEqual(PRIORITY[0], "jaw")
        self.assertLess(PRIORITY.index("blink"), PRIORITY.index("angry"))
        self.assertLess(PRIORITY.index("angry"), PRIORITY.index("puno"))

    def test_rest_emits_nothing(self) -> None:
        self.assertEqual(play(self.arbiter, hold(5.0)), [])

    def test_head_turn_is_only_cuello(self) -> None:
        # Yaw, plus the small body movement and neck EMG that also reach puno and angry.
        turn = hold(0.4, cuello=-30, yaw=30, pitch=5, motion=20, puno=5, angry=8) + hold(2.0)
        self.assertEqual(play(self.arbiter, turn), ["cuello"])

    def test_arm_raise_is_brazos_not_cuello(self) -> None:
        arm = hold(0.4, brazos=-25, cuello=-20, pitch=25, yaw=15, motion=30) + hold(2.0)
        self.assertEqual(play(self.arbiter, arm), ["brazos"])

    def test_rejected_higher_input_lets_the_next_one_through(self) -> None:
        # brazos crosses its threshold but the movement is almost pure yaw: it was the neck.
        turn = hold(0.4, brazos=-12, cuello=-30, pitch=3, yaw=30, motion=20) + hold(2.0)
        self.assertEqual(play(self.arbiter, turn), ["cuello"])

    def test_frown_is_angry_even_if_the_head_tips(self) -> None:
        frown = hold(0.6, angry=10, frontal_ratio=0.6, brazos=-12, pitch=12, motion=10) + hold(2.0)
        self.assertEqual(play(self.arbiter, frown), ["angry"])

    def test_facial_emg_without_the_frown_pattern_is_not_angry(self) -> None:
        smile = hold(0.6, angry=10, frontal_ratio=1.05) + hold(2.0)
        self.assertEqual(play(self.arbiter, smile), [])

    def test_closing_the_eyes_is_not_a_blink(self) -> None:
        close = hold(0.3, blink=50) + hold(1.6, cerrar_ojos=5) + hold(1.0)
        self.assertEqual(play(self.arbiter, close), ["cerrar_ojos"])

    def test_blink_with_a_short_alpha_leak_is_still_a_blink(self) -> None:
        blink = hold(0.3, blink=50) + hold(0.3, cerrar_ojos=5) + hold(1.5)
        self.assertEqual(play(self.arbiter, blink), ["blink"])

    def test_clench_onset_is_not_a_blink(self) -> None:
        clench = hold(0.3, blink=50, jaw=20, jaw_emg=20) + hold(0.8, jaw=60, jaw_emg=60) + hold(1.5)
        self.assertEqual(play(self.arbiter, clench), ["jaw"])

    def test_fist_with_a_big_movement_is_dropped(self) -> None:
        self.assertEqual(play(self.arbiter, hold(0.4, puno=5, motion=15) + hold(1.5)), [])
        self.assertEqual(play(InputArbiter(params=PARAMS), hold(0.4, puno=5, motion=5) + hold(1.5)), ["puno"])

    def test_gesture_inside_the_refractory_is_ignored(self) -> None:
        frames = hold(0.3, blink=50) + hold(0.7) + hold(0.3, blink=50) + hold(2.0)
        self.assertEqual(play(self.arbiter, frames), ["blink"])

    def test_two_gestures_apart_both_count(self) -> None:
        frames = hold(0.3, blink=50) + hold(2.5) + hold(0.3, blink=50) + hold(1.5)
        self.assertEqual(play(self.arbiter, frames), ["blink", "blink"])

    def test_subset_threshold_override_and_unknown_input(self) -> None:
        arbiter = InputArbiter(("blink", "jaw"), params=PARAMS)
        self.assertEqual(arbiter.inputs, ("jaw", "blink"))
        arbiter.with_threshold("blink", 100.0)
        self.assertEqual(play(arbiter, hold(0.3, blink=50) + hold(1.5)), [])
        with self.assertRaises(ValueError):
            InputArbiter(("blink", "nope"))

    def test_missing_gauge_is_a_clear_error(self) -> None:
        arbiter = InputArbiter(("cuello",), params=PARAMS)
        with self.assertRaises(KeyError):
            for i in range(30):
                arbiter.update({"cuello": -30.0 if i < 10 else 0.0}, i * STEP)


class CeilingTest(unittest.TestCase):
    def test_activation_above_ceiling_is_discarded(self) -> None:
        params = ArtifactParams(threshold=2.0, min_s=0.1, ceiling=8.0)
        too_big = [0, 5, 20, 5, 0, 0]
        fine = [0, 5, 6, 5, 0, 0]
        detector = ThresholdDetector(params)
        self.assertFalse(any(detector.update(v, i * STEP) for i, v in enumerate(too_big)))
        detector = ThresholdDetector(params)
        self.assertTrue(any(detector.update(v, i * STEP) for i, v in enumerate(fine)))


class CalibrationTest(unittest.TestCase):
    def test_save_merges_and_load_applies(self) -> None:
        path = Path(tempfile.mkdtemp()) / "thresholds.json"
        self.assertEqual(calibration.load(path), {})
        calibration.save({"jaw": 35.0, "blink": 25.0}, path)
        calibration.save({"blink": 28.0}, path)  # recalibrating one input keeps the others
        self.assertEqual(calibration.load(path), {"jaw": 35.0, "blink": 28.0})
        params = calibration.calibrated_params(path)
        self.assertEqual(params["blink"].threshold, 28.0)
        self.assertEqual(params["cuello"].threshold, ARTIFACT_PARAMS["cuello"].threshold)

    def test_replay_and_score(self) -> None:
        ticks = 150
        times = np.arange(ticks) * STEP
        values = {name: np.zeros(ticks) for name in ("blink",)}
        values["blink"][20:28] = 50.0
        gauges = {k: np.full(ticks, v) for k, v in QUIET_GAUGES.items()}
        segment = (times, values, gauges)
        counts = calibration.replay(segment, ("blink",), PARAMS)
        self.assertEqual(counts, {"blink": 1})
        own = {"blink": ("blink",)}
        self.assertEqual(calibration.score({"blink": counts}, ("blink",), own, {"blink": 1}), 1.0)
        self.assertEqual(calibration.score({"rest": counts}, ("blink",), own, {}), -calibration.REST_PENALTY)


if __name__ == "__main__":
    unittest.main()
