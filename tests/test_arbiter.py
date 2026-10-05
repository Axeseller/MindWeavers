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
    "cuello": ArtifactParams(threshold=14.0, min_s=0.1, direction=-1, refractory_s=0.2),
    "blink": ArtifactParams(threshold=30.0, max_s=0.8, refractory_s=0.2),
    "angry": ArtifactParams(threshold=6.0, min_s=0.2, ceiling=25.0, refractory_s=0.2),
    "happy": ArtifactParams(threshold=2.0, min_s=0.2, ceiling=10.0, refractory_s=0.2),
    "puno": ArtifactParams(threshold=2.0, min_s=0.1, ceiling=8.0, refractory_s=0.2),
}
QUIET_VALUES = {name: 0.0 for name in PRIORITY}
QUIET_GAUGES = {"motion": 0.5, "pitch": 0.0, "yaw": 0.0, "jaw_emg": 2.0, "frontal_ratio": 1.0, "alpha": 1.5, "blink_fz": 10.0}


def play(arbiter: InputArbiter, frames: list[dict[str, float]]) -> list[str]:
    """Feed one frame per 40 ms tick (anything missing is at rest) and return the emitted inputs."""
    out = []
    for i, frame in enumerate(frames):
        values = {k: frame.get(k, 0.0) for k in arbiter.inputs}  # like the flight: only the enabled inputs
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
        self.assertLess(PRIORITY.index("blink"), PRIORITY.index("happy"))
        self.assertEqual(PRIORITY[-1], "puno")
        self.assertNotIn("brazos", PRIORITY)

    def test_rest_emits_nothing(self) -> None:
        self.assertEqual(play(self.arbiter, hold(5.0)), [])

    def test_head_turn_is_only_cuello(self) -> None:
        # Yaw, plus the small body movement and neck EMG that also reach puno and angry.
        turn = hold(0.4, cuello=-30, yaw=30, pitch=5, motion=20, puno=5, angry=8) + hold(2.0)
        self.assertEqual(play(self.arbiter, turn), ["cuello"])

    def test_arm_raise_is_not_cuello(self) -> None:
        arm = hold(0.4, cuello=-20, pitch=25, yaw=15, motion=30) + hold(2.0)
        self.assertEqual(play(self.arbiter, arm), [])

    def test_rejected_higher_input_lets_the_next_one_through(self) -> None:
        # angry crosses its threshold but with a smile's EMG pattern: happy gets through.
        smile = hold(0.6, angry=7, happy=4, frontal_ratio=1.1) + hold(2.0)
        self.assertEqual(play(self.arbiter, smile), ["happy"])

    def test_frown_is_angry_not_happy(self) -> None:
        frown = hold(0.6, angry=10, happy=4, frontal_ratio=0.6, pitch=8, motion=7) + hold(2.0)
        self.assertEqual(play(self.arbiter, frown), ["angry"])

    def test_smile_is_happy(self) -> None:
        smile = hold(0.6, happy=3, frontal_ratio=1.1) + hold(2.0)
        self.assertEqual(play(self.arbiter, smile), ["happy"])

    def test_closing_the_eyes_is_not_angry_or_happy(self) -> None:
        # Short closure (cerrar_ojos never fires) that squeezes the face: alpha gives it away.
        squeeze = hold(0.6, angry=10, happy=4, frontal_ratio=0.7, alpha=9) + hold(2.0)
        self.assertEqual(play(self.arbiter, squeeze), [])

    def test_blink_leaking_into_the_smile_band_is_not_happy(self) -> None:
        blink = hold(0.3, happy=3, blink_fz=40) + hold(2.0)
        self.assertEqual(play(InputArbiter(("happy",), params=PARAMS), blink), [])

    def test_closing_the_eyes_is_not_a_blink(self) -> None:
        close = hold(0.3, blink=50) + hold(1.6, cerrar_ojos=5) + hold(1.0)
        self.assertEqual(play(self.arbiter, close), ["cerrar_ojos"])

    def test_without_cerrar_ojos_closing_the_eyes_is_not_a_blink(self) -> None:
        arbiter = InputArbiter(("jaw", "cuello", "blink"), params=PARAMS)
        close = hold(0.3, blink=50, alpha=4) + hold(1.6, alpha=9) + hold(1.0)
        self.assertEqual(play(arbiter, close), [])
        self.assertEqual(play(InputArbiter(("jaw", "cuello", "blink"), params=PARAMS), hold(0.3, blink=50) + hold(1.5)), ["blink"])

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


class FaceCalibrationTest(unittest.TestCase):
    """A person whose frown is frontal (ratio ~1.4) and whose smile is not (~0.7): the opposite of the recordings."""

    def setUp(self) -> None:
        from eeg import arbiter as arbiter_module

        self.limits = arbiter_module.FACE_LIMITS
        self.saved = dict(self.limits)

    def tearDown(self) -> None:
        self.limits.clear()
        self.limits.update(self.saved)

    def face_segment(self, name: str, ratio: float, blink: float) -> calibration.Segment:
        ticks = 400
        times = np.arange(ticks) * STEP
        values = {n: np.zeros(ticks) for n in ("angry", "happy")}
        gauges = {k: np.full(ticks, v) for k, v in QUIET_GAUGES.items()}
        level = 12.0 if name == "angry" else 4.0
        for start in range(20, ticks - 40, 60):  # a face every 2.4 s, held 0.6 s
            values[name][start : start + 15] = level
            gauges["frontal_ratio"][start : start + 15] = ratio
            gauges["blink_fz"][start : start + 15] = blink
        return times, values, gauges

    def test_default_gates_reject_this_person(self) -> None:
        frown = hold(0.6, angry=10, frontal_ratio=1.4) + hold(2.0)
        self.assertEqual(play(InputArbiter(params=PARAMS), frown), [])

    def test_calibration_flips_the_boundary_and_accepts_them(self) -> None:
        segments = {"angry": self.face_segment("angry", 1.4, 12), "happy": self.face_segment("happy", 0.7, 30)}
        limits = calibration.fit_face_limits(segments, {"angry": ("angry",), "happy": ("happy",)}, log=lambda *_: None)
        self.assertFalse(limits["frown_is_low"])
        self.assertAlmostEqual(limits["face_ratio"], 1.05, places=2)
        self.assertGreaterEqual(limits["smile_max_blink"], 30 * 1.3 - 0.1)
        calibration.apply_gates(limits)
        frown = hold(0.6, angry=10, frontal_ratio=1.4) + hold(2.0)
        smile = hold(0.6, happy=4, frontal_ratio=0.7, blink_fz=30) + hold(2.0)
        self.assertEqual(play(InputArbiter(params=PARAMS), frown), ["angry"])
        self.assertEqual(play(InputArbiter(params=PARAMS), smile), ["happy"])

    def test_gates_are_saved_and_loaded(self) -> None:
        path = Path(tempfile.mkdtemp()) / "thresholds.json"
        calibration.save({"angry": 5.0}, path, gates={"face_ratio": 1.2, "frown_is_low": False})
        calibration.save({"happy": 1.5}, path)  # a later threshold-only save keeps the gates
        self.assertTrue(calibration.apply_saved_gates(path))
        self.assertEqual(self.limits["face_ratio"], 1.2)
        self.assertFalse(self.limits["frown_is_low"])


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
