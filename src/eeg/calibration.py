"""Per-session thresholds: for each input, the threshold that makes the whole arbiter (what fly.py runs) read
this person's session best, saved so the scripts load it.

The session is a set of segments, one per prompted input plus "rest". A set of thresholds is scored by replaying
every segment through InputArbiter: repetitions caught in the input's own segment, minus firings anywhere else,
with firings at rest weighted heavily. Thresholds are tuned one input at a time, twice over (coordinate search).
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import numpy as np

from eeg import arbiter as arbiter_module
from eeg.arbiter import InputArbiter
from eeg.detectors import ARTIFACT_PARAMS, ArtifactParams, ThresholdDetector

DEFAULT_PATH = Path(__file__).resolve().parents[2] / "data" / "calibration" / "thresholds.json"
SEARCH = (0.4, 3.0, 21)  # thresholds tried per input: tested default x 0.4 ... x 3, log spaced
PASSES = 2
REST_PENALTY = 10.0  # one command at rest costs as much as missing ten repetitions
CROSS_PENALTY = 1.0  # one wrong command costs one repetition

# A segment as replayed: tick times, every input's feature values, every gauge's values.
Segment = tuple[np.ndarray, dict[str, np.ndarray], dict[str, np.ndarray]]


def replay(segment: Segment, inputs: tuple[str, ...], params: dict[str, ArtifactParams]) -> dict[str, int]:
    """Commands the arbiter emits over one segment."""
    times, values, gauges = segment
    arbiter = InputArbiter(inputs, params=params)
    counts = {name: 0 for name in inputs}
    for i, now in enumerate(times):
        emitted = arbiter.update(
            {name: float(values[name][i]) for name in inputs}, float(now), {k: float(v[i]) for k, v in gauges.items()}
        )
        if emitted:
            counts[emitted] += 1
    return counts


def score(
    tables: dict[str, dict[str, int]], inputs: tuple[str, ...], own: dict[str, tuple[str, ...]], reps: dict[str, int]
) -> float:
    total = 0.0
    for label, counts in tables.items():
        for name in inputs:
            c = counts[name]
            if label in own[name]:
                total += min(c, reps.get(label, 0)) - max(0, c - reps.get(label, 0))
            else:
                total -= (REST_PENALTY if label == "rest" else CROSS_PENALTY) * c
    return total


def choose_thresholds(
    segments: dict[str, Segment],
    inputs: tuple[str, ...],
    own: dict[str, tuple[str, ...]],
    reps: dict[str, int],
    log=print,
) -> dict[str, float]:
    params = {name: ARTIFACT_PARAMS[name] for name in inputs}

    def evaluate(candidate: dict[str, ArtifactParams]) -> float:
        return score({label: replay(s, inputs, candidate) for label, s in segments.items()}, inputs, own, reps)

    best = evaluate(params)
    log(f"  start score {best:.0f}")
    lo, hi, n = SEARCH
    for round_ in range(PASSES):
        for name in inputs:
            default = ARTIFACT_PARAMS[name].threshold
            for threshold in default * np.geomspace(lo, hi, n):
                trial = {**params, name: replace(params[name], threshold=float(round(threshold, 3)))}
                value = evaluate(trial)
                closer = abs(np.log(threshold / default)) < abs(np.log(params[name].threshold / default))
                if value > best or (value == best and closer):
                    best, params = value, trial
            log(f"  pass {round_ + 1}  {name:12s} -> {params[name].threshold:8.2f}   score {best:.0f}")
    return {name: params[name].threshold for name in inputs}


MIN_FACES = 3  # repetitions needed to fit a face gate


def face_peaks(segment: Segment, name: str) -> list[tuple[float, float]]:
    """(frontal/occipital ratio at the peak, max eye deflection) for each activation of a face input, found with
    its threshold only (no gates). Lowers the threshold when the person's EMG is weaker than tested."""
    times, values, gauges = segment
    for scale in (1.0, 0.7, 0.5, 0.35):
        detector = ThresholdDetector(replace(ARTIFACT_PARAMS[name], threshold=ARTIFACT_PARAMS[name].threshold * scale))
        found, start = [], 0
        for i, (t, v) in enumerate(zip(times, values[name])):
            was = detector.active
            fired = detector.update(float(v), float(t))
            if detector.active and not was:
                start = i
            if fired:
                peak = start + int(np.argmax(values[name][start : i + 1]))
                found.append((float(gauges["frontal_ratio"][peak]), float(np.max(gauges["blink_fz"][start : i + 1]))))
        if len(found) >= MIN_FACES:
            return found
    return found


def fit_face_limits(segments: dict[str, Segment], own: dict[str, tuple[str, ...]], log=print) -> dict:
    """Face gate limits for this person: the frown/smile boundary sits between their own frowns and smiles."""
    limits = dict(arbiter_module.FACE_LIMITS)
    peaks = {}
    for name in ("angry", "happy"):
        labels = [label for label in own.get(name, ()) if label in segments]
        peaks[name] = [p for label in labels for p in face_peaks(segments[label], name)]
    frown = [ratio for ratio, _ in peaks["angry"]]
    smile = [ratio for ratio, _ in peaks["happy"]]
    if len(frown) >= MIN_FACES and len(smile) >= MIN_FACES:
        frown_med, smile_med = float(np.median(frown)), float(np.median(smile))
        limits["frown_is_low"] = frown_med < smile_med
        limits["face_ratio"] = round((frown_med + smile_med) / 2, 3)
        log(f"  frown pattern {frown_med:.2f}, smile pattern {smile_med:.2f} -> boundary {limits['face_ratio']:.2f}")
        if abs(frown_med - smile_med) < 0.1:
            log("  [!] your frown and smile look alike to the headset: they may confuse each other")
    elif peaks["angry"] or peaks["happy"]:
        log("  [!] not enough frowns or smiles to fit the face pattern; keeping the tested boundary")
    if len(peaks["happy"]) >= MIN_FACES:
        blinks = [blink for _, blink in peaks["happy"]]
        limits["smile_max_blink"] = round(max(22.0, 1.3 * float(np.percentile(blinks, 90))), 1)
        log(f"  eye deflection while smiling up to {max(blinks):.0f} -> allowed {limits['smile_max_blink']:.0f}")
    return limits


def apply_gates(limits: dict) -> None:
    arbiter_module.FACE_LIMITS.update({k: v for k, v in limits.items() if k in arbiter_module.FACE_LIMITS})


def apply_saved_gates(path: Path = DEFAULT_PATH) -> bool:
    """Use the face limits of the saved calibration, if it has them. Returns whether it did."""
    if not path.exists():
        return False
    gates = json.loads(path.read_text()).get("gates", {})
    apply_gates(gates)
    return bool(gates)


def save(thresholds: dict[str, float], path: Path = DEFAULT_PATH, note: str = "", gates: dict | None = None) -> Path:
    """Write the thresholds (and face limits), keeping any saved ones for inputs not in `thresholds`."""
    previous = json.loads(path.read_text()) if path.exists() else {}
    merged = {**load(path), **thresholds}
    data = {"note": note, "thresholds": merged, "gates": {**previous.get("gates", {}), **(gates or {})}}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))
    return path


def load(path: Path = DEFAULT_PATH) -> dict[str, float]:
    """Saved thresholds, or {} when there is no calibration."""
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    return {name: float(value) for name, value in data.get("thresholds", {}).items() if name in ARTIFACT_PARAMS}


def calibrated_params(path: Path = DEFAULT_PATH) -> dict[str, ArtifactParams]:
    """ARTIFACT_PARAMS with the saved thresholds applied."""
    saved = load(path)
    return {name: replace(p, threshold=saved.get(name, p.threshold)) for name, p in ARTIFACT_PARAMS.items()}
