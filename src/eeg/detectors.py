from __future__ import annotations

from dataclasses import dataclass

from mapping.commands import Event


@dataclass
class DetectorConfig:
    jaw_rms_threshold: float = 40.0
    jaw_short_min: float = 0.25
    jaw_short_max: float = 1.0
    jaw_long_min: float = 1.2
    jaw_emergency_min: float = 2.5
    blink_peak_threshold: float = 80.0
    blink_pair_window: float = 0.5
    emit_single_blink: bool = False
    eyes_closed_threshold: float = float("inf")
    eyes_closed_min_s: float = 2.0
    refractory_s: float = 0.8
    release_ratio: float = 0.6


JAW_TAKEOFF_THRESHOLD = 40.0
BLINK_PHOTO_THRESHOLD = 55.0
EYES_CLOSED_THRESHOLD = 6.0


def jaw_takeoff_config(threshold: float = JAW_TAKEOFF_THRESHOLD) -> DetectorConfig:
    """Calibrated from rest/jaw baselines: rest never exceeds ~30, a clench stays above 40 for ~0.7-1.1 s."""
    return DetectorConfig(
        jaw_rms_threshold=threshold,
        jaw_short_min=0.5,
        jaw_short_max=2.0,
        jaw_long_min=2.0,
        jaw_emergency_min=10.0,
        blink_peak_threshold=float("inf"),
        eyes_closed_threshold=float("inf"),
    )


def camera_blink_config(
    blink_threshold: float = BLINK_PHOTO_THRESHOLD,
    eyes_closed_threshold: float = EYES_CLOSED_THRESHOLD,
) -> DetectorConfig:
    """Calibrated from blink3secinterval / cerrarojos3sec / baselineojoscerrados."""
    return DetectorConfig(
        jaw_rms_threshold=float("inf"),
        blink_peak_threshold=blink_threshold,
        emit_single_blink=True,
        blink_pair_window=0.0,
        eyes_closed_threshold=eyes_closed_threshold,
        eyes_closed_min_s=2.0,
        refractory_s=0.8,
    )


class ArtifactDetector:
    """Heuristic state machines. Tune thresholds from baseline recordings."""

    def __init__(self, config: DetectorConfig | None = None) -> None:
        self.config = config or DetectorConfig()
        self._jaw_active = False
        self._jaw_started_at = 0.0
        self._last_blink_at = 0.0
        self._blink_open = False
        self._eyes_closed = False
        self._eyes_started_at = 0.0
        self._eyes_emitted = False
        self._refractory_until = 0.0

    @property
    def jaw_active(self) -> bool:
        return self._jaw_active

    @property
    def eyes_closed(self) -> bool:
        return self._eyes_closed

    def update(
        self,
        jaw_rms: float,
        blink_amp: float,
        timestamp: float,
        eyes_closed_amp: float = 0.0,
    ) -> list[str]:
        events: list[str] = []
        eyes_event = self._update_eyes_closed(eyes_closed_amp, timestamp)
        if eyes_event:
            events.append(eyes_event)
        if timestamp >= self._refractory_until:
            events.extend(self._update_gated(jaw_rms, blink_amp, timestamp))
        return events

    def _update_gated(self, jaw_rms: float, blink_amp: float, timestamp: float) -> list[str]:
        events: list[str] = []
        jaw_event = self._update_jaw(jaw_rms, timestamp)
        if jaw_event:
            events.append(jaw_event)
        if not self._eyes_closed:
            blink_event = self._update_blink(blink_amp, timestamp)
            if blink_event:
                events.append(blink_event)
        if events:
            self._refractory_until = timestamp + self.config.refractory_s
        return events

    def _update_jaw(self, jaw_rms: float, timestamp: float) -> str | None:
        enter = self.config.jaw_rms_threshold
        leave = enter * self.config.release_ratio
        if not self._jaw_active and jaw_rms >= enter:
            self._jaw_active = True
            self._jaw_started_at = timestamp
            return None
        if not self._jaw_active:
            return None
        duration = timestamp - self._jaw_started_at
        if duration >= self.config.jaw_emergency_min:
            self._jaw_active = False
            return Event.JAW_EMERGENCY
        if jaw_rms < leave:
            self._jaw_active = False
            return self._classify_jaw(duration)
        return None

    def _classify_jaw(self, duration: float) -> str | None:
        if duration >= self.config.jaw_emergency_min:
            return Event.JAW_EMERGENCY
        if duration >= self.config.jaw_long_min:
            return Event.JAW_LONG
        if self.config.jaw_short_min <= duration <= self.config.jaw_short_max:
            return Event.JAW_SHORT
        return None

    def _update_blink(self, blink_amp: float, timestamp: float) -> str | None:
        enter = self.config.blink_peak_threshold
        leave = enter * self.config.release_ratio
        if not self._blink_open and blink_amp >= enter:
            self._blink_open = True
            if self.config.emit_single_blink:
                return Event.BLINK
            return self._register_blink(timestamp)
        if self._blink_open and blink_amp < leave:
            self._blink_open = False
        return None

    def _update_eyes_closed(self, eyes_closed_amp: float, timestamp: float) -> str | None:
        enter = self.config.eyes_closed_threshold
        leave = enter * self.config.release_ratio
        if not self._eyes_closed and eyes_closed_amp >= enter:
            self._eyes_closed = True
            self._eyes_started_at = timestamp
            self._eyes_emitted = False
            return None
        if not self._eyes_closed:
            return None
        if not self._eyes_emitted and timestamp - self._eyes_started_at >= self.config.eyes_closed_min_s:
            self._eyes_emitted = True
            return Event.EYES_CLOSED
        if eyes_closed_amp < leave:
            self._eyes_closed = False
            if self._eyes_emitted:
                return Event.EYES_OPENED
        return None

    def _register_blink(self, timestamp: float) -> str | None:
        gap = timestamp - self._last_blink_at
        self._last_blink_at = timestamp
        if 0 < gap <= self.config.blink_pair_window:
            self._last_blink_at = 0.0
            return Event.DOUBLE_BLINK
        return None


# ---------------------------------------------------------------------------
# One detector per recorded artifact. The feature comes from eeg.preprocess.ARTIFACT_CLEANING[name];
# these are the decision parameters, tuned on the 2026-10-04 recordings through the arbiter
# (scripts/artifacts/calibrate.py --recordings). A per-session calibration overrides the thresholds.
# ---------------------------------------------------------------------------
INF = float("inf")


@dataclass(frozen=True)
class ArtifactParams:
    """When a feature value counts as the artifact.

    threshold:    the feature must reach this to start an activation.
    min_s/max_s:  how long the activation must last. Shorter or longer is ignored.
    hold:         fire once while still active after min_s (eyes closed), instead of on release.
    direction:    0 for a magnitude. +1/-1 for a signed feature: only an onset of that sign fires,
                  and an onset of the other sign still starts the refractory so its return is not read.
    ceiling:      if the activation ever exceeds this, it was a bigger artifact and is discarded.
    refractory_s: nothing new starts until this long after an activation ends.
    release_ratio: the activation ends when the feature drops below threshold * release_ratio.
    """

    threshold: float
    min_s: float = 0.0
    max_s: float = INF
    hold: bool = False
    direction: int = 0
    ceiling: float = INF
    refractory_s: float = 1.0
    release_ratio: float = 0.6


ARTIFACT_PARAMS: dict[str, ArtifactParams] = {
    "jaw": ArtifactParams(threshold=JAW_TAKEOFF_THRESHOLD, min_s=0.5, max_s=2.0, refractory_s=0.8),
    "blink": ArtifactParams(threshold=30.0, max_s=0.8, refractory_s=0.8),
    "cerrar_ojos": ArtifactParams(threshold=3.3, min_s=1.5, hold=True, refractory_s=1.0),
    "cuello": ArtifactParams(threshold=10.0, min_s=0.1, refractory_s=1.5),
    "puno": ArtifactParams(threshold=2.5, min_s=0.15, ceiling=8.0, refractory_s=1.5),
    "angry": ArtifactParams(threshold=6.0, min_s=0.2, ceiling=25.0, refractory_s=1.5),
    "happy": ArtifactParams(threshold=2.0, min_s=0.2, ceiling=10.0, refractory_s=1.5),
}


class ThresholdDetector:
    """Hysteresis + duration + refractory on one feature. `update` returns True when the artifact is detected;
    `peak` is then the strongest value of that activation."""

    def __init__(self, params: ArtifactParams) -> None:
        self.params = params
        self._active = False
        self._sign = 0
        self._started_at = 0.0
        self._emitted = False
        self._refractory_until = 0.0
        self.peak = 0.0

    @property
    def active(self) -> bool:
        return self._active

    @property
    def started_at(self) -> float:
        """When the current (or last) activation began."""
        return self._started_at

    def update(self, value: float, timestamp: float) -> bool:
        p = self.params
        level = abs(value) if p.direction else value
        if not self._active:
            if timestamp < self._refractory_until or level < p.threshold:
                return False
            self._active = True
            self._sign = 1 if value >= 0 else -1
            self._started_at = timestamp
            self._emitted = False
            self.peak = value
            return False

        if level > abs(self.peak):
            self.peak = value
        duration = timestamp - self._started_at
        wanted = not p.direction or self._sign == p.direction
        if p.hold and wanted and not self._emitted and duration >= p.min_s and abs(self.peak) <= p.ceiling:
            self._emitted = True
            return True
        if level >= p.threshold * p.release_ratio:
            return False

        self._active = False
        self._refractory_until = timestamp + p.refractory_s
        if p.hold or not wanted or abs(self.peak) > p.ceiling:
            return False
        return p.min_s <= duration <= p.max_s
