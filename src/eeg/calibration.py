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

from eeg.arbiter import InputArbiter
from eeg.detectors import ARTIFACT_PARAMS, ArtifactParams

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


def save(thresholds: dict[str, float], path: Path = DEFAULT_PATH, note: str = "") -> Path:
    """Write the thresholds, keeping any saved ones for inputs not in `thresholds`."""
    merged = {**load(path), **thresholds}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"note": note, "thresholds": merged}, indent=2))
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
