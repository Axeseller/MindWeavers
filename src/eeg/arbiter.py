"""One decision from several artifact detectors running on the same stream.

Every detector only knows its own feature, so one gesture can fire several of them: a head turn is also a small
body movement (puno) and some neck EMG (angry, happy); closing the eyes starts like a blink and squeezes the
face (angry); a blink leaks into the smile band (happy). The arbiter turns their firings into at most one input at a time:

1. A firing becomes a *candidate* for `confirm_s` instead of acting at once.
2. Priority: the highest-priority candidate that passes its gate wins; the others are dropped. While a
   higher-priority detector is still active (eyes still closed, arm still moving), the decision waits, since it
   may still fire. A candidate rejected by its gate lets the next one in line through.
3. Gates: from onset until the decision the arbiter tracks gauges (eeg.preprocess.GAUGE_CLEANING) and every
   input's feature, then checks the input's GATES. A neck turn must be mostly yaw, a frown and a smile must have
   their own EMG pattern with the eyes open, faint inputs must come without a big head movement.
4. Once emitted, everything is ignored for `refractory_s`, including activations that started before it ended
   (the return swing of a movement).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from eeg.detectors import ARTIFACT_PARAMS, ArtifactParams, ThresholdDetector

#: Highest priority first. A higher one wins over, or cancels, a lower one that fires at the same time.
#: blink sits above angry, happy and puno because a wrong photo is harmless and a wrong pulse moves the drone.
PRIORITY: tuple[str, ...] = ("jaw", "cerrar_ojos", "cuello", "blink", "angry", "happy", "puno")
CONFIRM_S = 0.5
MAX_WAIT_S = 2.0
REFRACTORY_S = 1.0

# A gate gets what was seen from the input's onset until now: the largest |value| of every gauge and input
# feature (`peak`), and every value at the tick where the input's own feature peaked (`at_peak`).
# It returns why the firing is not that input, or None to accept it.
Seen = dict[str, float]
Gate = Callable[[Seen, Seen], "str | None"]

MOTION_LIMIT = 8.0  # gyroscope magnitude; a fist or a blink barely moves the head
ANGRY_MOTION_LIMIT = 12.0  # frowning tilts the head a little
JAW_EMG_LIMIT = 15.0  # a clench starting leaks into the blink band
NECK_MAX_PITCH = 0.6  # neck turn: pitch at most 0.6 x yaw (measured <= 0.27; raising an arm >= 0.73)
FROWN_MAX_RATIO = 0.85  # frown: frontal/occipital EMG at its peak (measured 0.47-0.88; others >= 0.89)
SMILE_MIN_RATIO = 0.9  # smile: frontal/occipital EMG at its peak (measured 0.90-1.30; frown ~0.6, arm ~0.75)
EYES_OPEN_ALPHA = 5.0  # alpha above this means the eyes were closed (frown/smile 1-3, eyes closed 8-14)
SMILE_MAX_BLINK = 22.0  # frontal eye deflection during a smile is 13-20; a blink is 25-72


def _gate_cuello(peak: Seen, at_peak: Seen) -> str | None:
    if peak["pitch"] > NECK_MAX_PITCH * peak["yaw"]:
        return f"pitch {peak['pitch']:.0f} vs yaw {peak['yaw']:.0f}: an arm, not the neck"
    return None


def _gate_angry(peak: Seen, at_peak: Seen) -> str | None:
    if peak["motion"] > ANGRY_MOTION_LIMIT:
        return f"head moved {peak['motion']:.1f}"
    if peak["alpha"] > EYES_OPEN_ALPHA:
        return f"alpha {peak['alpha']:.1f}: the eyes were closed"
    if at_peak["frontal_ratio"] > FROWN_MAX_RATIO:
        return f"frontal/occipital EMG {at_peak['frontal_ratio']:.2f}: not a frown pattern"
    return None


def _gate_happy(peak: Seen, at_peak: Seen) -> str | None:
    if peak["motion"] > MOTION_LIMIT:
        return f"head moved {peak['motion']:.1f}"
    if peak["alpha"] > EYES_OPEN_ALPHA:
        return f"alpha {peak['alpha']:.1f}: the eyes were closed"
    if peak["jaw_emg"] > JAW_EMG_LIMIT:
        return f"jaw EMG {peak['jaw_emg']:.1f}: a clench"
    if peak["blink_fz"] > SMILE_MAX_BLINK:
        return f"eye deflection {peak['blink_fz']:.0f}: a blink"
    if at_peak["frontal_ratio"] < SMILE_MIN_RATIO:
        return f"frontal/occipital EMG {at_peak['frontal_ratio']:.2f}: a frown, not a smile"
    return None


def _gate_puno(peak: Seen, at_peak: Seen) -> str | None:
    if peak["motion"] > MOTION_LIMIT:
        return f"head moved {peak['motion']:.1f}"
    return None


def _gate_blink(peak: Seen, at_peak: Seen) -> str | None:
    if peak["motion"] > MOTION_LIMIT:
        return f"head moved {peak['motion']:.1f}"
    if peak["jaw_emg"] > JAW_EMG_LIMIT:
        return f"jaw EMG {peak['jaw_emg']:.1f}: a clench starting"
    # With cerrar_ojos enabled (its feature is in `peak`), priority already tells a closure from a blink and keeps
    # more blinks. Without it, closing the eyes would read as blinks, so alpha decides (costs ~1 blink in 4).
    if "cerrar_ojos" not in peak and peak["alpha"] > EYES_OPEN_ALPHA:
        return f"alpha {peak['alpha']:.1f}: the eyes were closed"
    return None


GATES: dict[str, Gate] = {
    "cuello": _gate_cuello,
    "angry": _gate_angry,
    "happy": _gate_happy,
    "puno": _gate_puno,
    "blink": _gate_blink,
}


class _Track:
    """What one input has seen since its onset."""

    def __init__(self, own: float, seen: Seen) -> None:
        self.own_peak = abs(own)
        self.peak = {k: abs(v) for k, v in seen.items()}
        self.at_peak = dict(seen)

    def add(self, own: float, seen: Seen) -> None:
        for k, v in seen.items():
            self.peak[k] = max(self.peak.get(k, 0.0), abs(v))
        if abs(own) >= self.own_peak:
            self.own_peak = abs(own)
            self.at_peak = dict(seen)


class InputArbiter:
    def __init__(
        self,
        inputs: tuple[str, ...] = PRIORITY,
        confirm_s: float = CONFIRM_S,
        max_wait_s: float = MAX_WAIT_S,
        refractory_s: float = REFRACTORY_S,
        params: dict[str, ArtifactParams] | None = None,
        gates: dict[str, Gate] | None = None,
    ) -> None:
        unknown = set(inputs) - set(PRIORITY)
        if unknown:
            raise ValueError(f"No priority for {sorted(unknown)}; add them to arbiter.PRIORITY")
        self.inputs = tuple(name for name in PRIORITY if name in inputs)
        self.confirm_s = confirm_s
        self.max_wait_s = max_wait_s
        self.refractory_s = refractory_s
        self.gates = GATES if gates is None else gates
        table = {**ARTIFACT_PARAMS, **(params or {})}
        self.detectors = {name: ThresholdDetector(table[name]) for name in self.inputs}
        self._candidates: dict[str, float] = {}  # input -> when it fired
        self._refractory_until = 0.0
        self._tracks: dict[str, _Track] = {}
        self.dropped: list[tuple[str, str]] = []  # (input, reason) since the last update, for logging

    def rank(self, name: str) -> int:
        return self.inputs.index(name)

    def active(self, name: str) -> bool:
        return self.detectors[name].active

    def with_threshold(self, name: str, threshold: float) -> None:
        detector = self.detectors[name]
        self.detectors[name] = ThresholdDetector(replace(detector.params, threshold=threshold))

    def update(self, values: dict[str, float], now: float, gauges: dict[str, float] | None = None) -> str | None:
        """Feed this tick's input features and gauges; return the input confirmed on this tick, if any."""
        self.dropped = []
        seen = {**values, **(gauges or {})}
        for name in self.inputs:
            detector = self.detectors[name]
            was_active = detector.active
            fired = detector.update(values[name], now)
            if detector.active and not was_active:
                self._tracks[name] = _Track(values[name], seen)
            elif name in self._tracks:
                self._tracks[name].add(values[name], seen)
            if fired:
                if detector.started_at < self._refractory_until:
                    self._drop(name, "started during refractory")
                else:
                    self._candidates[name] = now
            elif not detector.active and name not in self._candidates:
                self._tracks.pop(name, None)
        return self._decide(now)

    def _decide(self, now: float) -> str | None:
        for name in sorted(self._candidates, key=self.rank):
            reason = self._gate(name)
            if reason is None and now - self._candidates[name] > self.max_wait_s:
                reason = f"waited {self.max_wait_s} s"
            if reason:
                self._drop(name, reason)
                continue
            if any(self.detectors[h].active for h in self.inputs[: self.rank(name)]):
                return None
            if now - self._candidates[name] < self.confirm_s:
                return None
            for other in list(self._candidates):
                if other != name:
                    self._drop(other, f"{name} won")
            self._drop(name, None)
            self._refractory_until = now + self.refractory_s
            return name
        return None

    def _gate(self, name: str) -> str | None:
        gate = self.gates.get(name)
        track = self._tracks.get(name)
        if gate is None or track is None:
            return None
        try:
            return gate(track.peak, track.at_peak)
        except KeyError as missing:
            raise KeyError(f"gate for {name} needs gauge {missing}; pass it in update(gauges=...)") from None

    def _drop(self, name: str, reason: str | None) -> None:
        """Forget a candidate; `reason` None means it was emitted."""
        self._candidates.pop(name, None)
        self._tracks.pop(name, None)
        if reason:
            self.dropped.append((name, reason))
