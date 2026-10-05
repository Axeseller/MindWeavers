from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from eeg.arbiter import PRIORITY, InputArbiter  # noqa: E402
from eeg.detectors import ARTIFACT_PARAMS, ArtifactParams, ThresholdDetector  # noqa: E402

STEP = 0.04
PARAMS = {
    "jaw": ArtifactParams(threshold=40.0, min_s=0.2, max_s=2.0, refractory_s=0.2),
    "cerrar_ojos": ArtifactParams(threshold=3.0, min_s=1.0, hold=True, refractory_s=0.2),
    "cuello": ArtifactParams(threshold=17.0, min_s=0.1, direction=-1, refractory_s=0.2),
    "brazos": ArtifactParams(threshold=20.0, min_s=0.1, direction=-1, refractory_s=0.2),
    "blink": ArtifactParams(threshold=30.0, max_s=0.8, refractory_s=0.2),
    "angry": ArtifactParams(threshold=6.0, min_s=0.2, ceiling=25.0, refractory_s=0.2),
    "puno": ArtifactParams(threshold=2.0, min_s=0.1, ceiling=8.0, refractory_s=0.2),
}
QUIET = {name: 0.0 for name in PRIORITY}


def play(arbiter: InputArbiter, frames: list[dict[str, float]]) -> list[str]:
    """Feed one frame per 40 ms tick (missing inputs are 0) and return the emitted inputs."""
    out = []
    for i, frame in enumerate(frames):
        emitted = arbiter.update({**QUIET, **frame}, i * STEP)
        if emitted:
            out.append(emitted)
    return out


def hold(frame: dict[str, float], seconds: float) -> list[dict[str, float]]:
    return [frame] * int(round(seconds / STEP))


class ArbiterTest(unittest.TestCase):
    def setUp(self) -> None:
        self.arbiter = InputArbiter(params=PARAMS)

    def test_priority_order_puts_blink_above_angry_and_puno(self) -> None:
        self.assertLess(PRIORITY.index("blink"), PRIORITY.index("angry"))
        self.assertLess(PRIORITY.index("angry"), PRIORITY.index("puno"))
        self.assertEqual(PRIORITY[0], "jaw")

    def test_one_gesture_fires_one_input(self) -> None:
        # A head turn: yaw, plus a small body movement and some neck EMG at the same time.
        turn = hold({"cuello": -30.0, "puno": 5.0, "angry": 8.0}, 0.4) + hold({}, 2.0)
        self.assertEqual(play(self.arbiter, turn), ["cuello"])

    def test_closing_the_eyes_is_not_a_blink(self) -> None:
        # Frontal deflection first, alpha rises a little later and stays.
        close = hold({"blink": 50.0}, 0.3) + hold({"cerrar_ojos": 5.0}, 1.5) + hold({}, 1.0)
        self.assertEqual(play(self.arbiter, close), ["cerrar_ojos"])

    def test_a_blink_still_counts_when_alpha_releases_quickly(self) -> None:
        blink = hold({"blink": 50.0}, 0.3) + hold({"cerrar_ojos": 5.0}, 0.3) + hold({}, 1.5)
        self.assertEqual(play(self.arbiter, blink), ["blink"])

    def test_clench_onset_is_not_a_blink_or_a_frown(self) -> None:
        # The EMG step leaks into the blink band before the 1 s jaw RMS reaches its threshold.
        clench = hold({"blink": 50.0, "jaw": 20.0, "angry": 20.0}, 0.3) + hold({"jaw": 60.0, "angry": 60.0}, 0.8)
        self.assertEqual(play(self.arbiter, clench + hold({}, 1.5)), ["jaw"])

    def test_faint_inputs_are_dropped_when_the_head_moved(self) -> None:
        frown_while_moving = hold({"angry": 10.0, "puno": 15.0}, 0.5) + hold({}, 1.5)
        self.assertEqual(play(self.arbiter, frown_while_moving), [])
        self.assertIn(("angry", "head moved 15.0 > 12.0"), self.arbiter_dropped_history)

    def test_return_swing_is_ignored(self) -> None:
        turn = hold({"cuello": -30.0}, 0.3) + hold({}, 0.6) + hold({"cuello": 30.0, "puno": 3.0}, 0.3) + hold({}, 1.5)
        self.assertEqual(play(self.arbiter, turn), ["cuello"])

    def test_two_gestures_apart_both_count(self) -> None:
        frames = hold({"blink": 50.0}, 0.3) + hold({}, 2.5) + hold({"blink": 50.0}, 0.3) + hold({}, 1.5)
        self.assertEqual(play(self.arbiter, frames), ["blink", "blink"])

    def test_subset_and_threshold_override(self) -> None:
        arbiter = InputArbiter(("blink", "jaw"), params=PARAMS)
        self.assertEqual(arbiter.inputs, ("jaw", "blink"))
        arbiter.with_threshold("blink", 100.0)
        self.assertEqual(play(arbiter, hold({"blink": 50.0}, 0.3) + hold({}, 1.5)), [])
        with self.assertRaises(ValueError):
            InputArbiter(("blink", "nope"))

    @property
    def arbiter_dropped_history(self) -> list[tuple[str, str]]:
        return self._history

    def play_tracking(self, frames):  # pragma: no cover - helper kept simple
        return play(self.arbiter, frames)

    def run(self, result=None):
        # Collect every dropped reason across the test so assertions can look at them.
        self._history = []
        original = InputArbiter._drop

        def tracking_drop(arbiter, name, reason):
            original(arbiter, name, reason)
            self._history.append((name, reason))

        InputArbiter._drop = tracking_drop
        try:
            return super().run(result)
        finally:
            InputArbiter._drop = original


class CeilingTest(unittest.TestCase):
    def test_activation_above_ceiling_is_discarded(self) -> None:
        detector = ThresholdDetector(ArtifactParams(threshold=2.0, min_s=0.1, ceiling=8.0))
        fired = [detector.update(v, i * STEP) for i, v in enumerate([0, 5, 20, 5, 0, 0])]
        self.assertFalse(any(fired))
        detector = ThresholdDetector(ArtifactParams(threshold=2.0, min_s=0.1, ceiling=8.0))
        fired = [detector.update(v, i * STEP) for i, v in enumerate([0, 5, 6, 5, 0, 0])]
        self.assertTrue(any(fired))

    def test_real_params_have_sane_ceilings(self) -> None:
        for name in ("angry", "puno"):
            self.assertGreater(ARTIFACT_PARAMS[name].ceiling, ARTIFACT_PARAMS[name].threshold)


if __name__ == "__main__":
    unittest.main()
