"""One decision from several artifact detectors running on the same stream.

Every detector only knows its own feature, so one gesture can fire several of them: a head turn is also a small
body movement (puno) and some neck EMG (angry); closing the eyes starts like a blink. The arbiter turns their
firings into at most one input at a time:

1. A firing becomes *pending* for `confirm_s` instead of being emitted at once.
2. While pending, a firing from a higher-priority detector replaces it. If a higher-priority detector is still
   active (eyes still closed, arm still moving) the pending one waits: dropped if that detector then fires,
   emitted if it releases without firing, dropped after `max_wait_s` either way.
3. Inputs that are faint signals (angry, puno, blink) are dropped when the head moved a lot meanwhile
   (`MOTION_LIMIT`, gyroscope magnitude): that was a neck or arm movement.
4. Once emitted, everything is ignored for `refractory_s`, including activations that started before that
   refractory ended (the return swing of a movement).
"""

from __future__ import annotations

from dataclasses import replace

from eeg.detectors import ARTIFACT_PARAMS, ArtifactParams, ThresholdDetector

#: Highest priority first. A higher one wins over, or cancels, a lower one that fires at the same time.
#: blink sits above angry and puno because a wrong photo is harmless and a wrong pulse moves the drone.
PRIORITY: tuple[str, ...] = ("jaw", "cerrar_ojos", "brazos", "cuello", "blink", "angry", "puno")
#: Dropped when the gyroscope magnitude (the `puno` feature) exceeded this between onset and emission.
MOTION_LIMIT: dict[str, float] = {"angry": 12.0, "puno": 8.0, "blink": 8.0}
#: Dropped when the jaw EMG (the `jaw` feature) exceeded this between onset and emission: a clench starting.
EMG_LIMIT: dict[str, float] = {"blink": 15.0}
CONFIRM_S = 0.5
MAX_WAIT_S = 2.0
REFRACTORY_S = 1.0


class InputArbiter:
    def __init__(
        self,
        inputs: tuple[str, ...] = PRIORITY,
        confirm_s: float = CONFIRM_S,
        max_wait_s: float = MAX_WAIT_S,
        refractory_s: float = REFRACTORY_S,
        params: dict[str, ArtifactParams] | None = None,
    ) -> None:
        unknown = set(inputs) - set(PRIORITY)
        if unknown:
            raise ValueError(f"No priority for {sorted(unknown)}; add them to arbiter.PRIORITY")
        self.inputs = tuple(name for name in PRIORITY if name in inputs)
        self.confirm_s = confirm_s
        self.max_wait_s = max_wait_s
        self.refractory_s = refractory_s
        table = {**ARTIFACT_PARAMS, **(params or {})}
        self.detectors = {name: ThresholdDetector(table[name]) for name in self.inputs}
        self._pending: tuple[str, float] | None = None
        self._refractory_until = 0.0
        self._motion_peak: dict[str, float] = {}
        self._emg_peak: dict[str, float] = {}
        self.dropped: list[tuple[str, str]] = []  # (input, reason) since the last update, for logging

    def rank(self, name: str) -> int:
        return self.inputs.index(name)

    def active(self, name: str) -> bool:
        return self.detectors[name].active

    def with_threshold(self, name: str, threshold: float) -> None:
        detector = self.detectors[name]
        self.detectors[name] = ThresholdDetector(replace(detector.params, threshold=threshold))

    def update(
        self, values: dict[str, float], now: float, motion: float | None = None, emg: float | None = None
    ) -> str | None:
        """Feed this tick's feature values, plus the two gauges: gyroscope magnitude (`motion`, defaults to the
        `puno` value) and jaw EMG (`emg`, defaults to the `jaw` value). Returns the input confirmed on this tick."""
        self.dropped = []
        if motion is None:
            motion = values.get("puno", 0.0)
        if emg is None:
            emg = values.get("jaw", 0.0)
        for name in self.inputs:
            detector = self.detectors[name]
            was_active = detector.active
            fired = detector.update(values[name], now)
            if detector.active and not was_active:
                self._motion_peak[name] = motion
                self._emg_peak[name] = emg
            elif name in self._motion_peak:
                self._motion_peak[name] = max(self._motion_peak[name], motion)
                self._emg_peak[name] = max(self._emg_peak[name], emg)
            if not fired:
                continue
            if detector.started_at < self._refractory_until:
                self._drop(name, "started during refractory")
            elif self._pending is not None and self.rank(self._pending[0]) < self.rank(name):
                self._drop(name, f"{self._pending[0]} is pending")
            else:
                if self._pending is not None:
                    self._drop(self._pending[0], f"{name} fired")
                self._pending = (name, now)

        if self._pending is None:
            return None
        name, since = self._pending
        limit = MOTION_LIMIT.get(name)
        if limit is not None and self._motion_peak.get(name, 0.0) > limit:
            return self._drop_pending(f"head moved {self._motion_peak[name]:.1f} > {limit}")
        limit = EMG_LIMIT.get(name)
        if limit is not None and self._emg_peak.get(name, 0.0) > limit:
            return self._drop_pending(f"jaw EMG {self._emg_peak[name]:.1f} > {limit}")
        blockers = [higher for higher in self.inputs[: self.rank(name)] if self.detectors[higher].active]
        if blockers:
            if now - since > self.max_wait_s:
                return self._drop_pending(f"waited {self.max_wait_s} s for {blockers[0]}")
            return None
        if now - since < self.confirm_s:
            return None
        self._pending = None
        self._refractory_until = now + self.refractory_s
        return name

    def _drop(self, name: str, reason: str) -> None:
        self.dropped.append((name, reason))

    def _drop_pending(self, reason: str) -> None:
        assert self._pending is not None
        self._drop(self._pending[0], reason)
        self._pending = None
        return None
