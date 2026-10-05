"""Live gesture -> flight command, from the Unicorn raw LSL stream.

    python live_classifier.py --model models/brazos.joblib      # live LSL
    python live_classifier.py --model models/cabeza.joblib --replay happy.csv

Prints one line per decision. It never talks to the drone: it only names the
flight function, so it can be wired into the app later.

How a decision is made
  1. Activity level (EMG 30-100 Hz + gyro) is tracked against a rolling 20 s
     median/MAD. A gesture starts when it crosses `onset_z` AND beats the
     absolute floor measured on the rest recording.
  2. Once enough signal has arrived (~1.5 s for fists/arms, ~1.5 s for head),
     the windows around the activity peak are cut out.
  3. The trained inputs are told apart, in one stage or by group then
     left/right, whichever validated better for this selection.
  4. A window unlike every trained gesture (novelty distance) is rejected first;
     then stage A rejects movements that are not a gesture (returns, releases).
     If any stage is below its confidence gate the answer is UNSURE and no
     command is emitted. Then nothing is accepted for that input's refractory time.
"""

from __future__ import annotations

import argparse
import os
import time
from collections import deque

import joblib
import numpy as np

import pipeline as P

HERE = os.path.dirname(os.path.abspath(__file__))
MIN_CHANNELS = 14              # 8 EEG + 3 accelerometer + 3 gyroscope

FS = P.FS
STREAM_NAME = "UnicornRecorderRawDataLSLStream"
TICK = 10                      # samples per update (40 ms)
BUFFER_S = 4.0                 # raw samples kept
ACTIVITY_S = 0.1               # level = mean activity of the newest 100 ms
PEAK_SEARCH_S = 0.7            # the activity peak is looked for up to this long after onset

#: Gesture -> flight function comes from the trained model (train.py SETS).
#: Put an entry here to override one without retraining.
FLIGHT_OVERRIDE: dict[str, str] = {}


class GestureClassifier:
    def __init__(self, bundle: dict) -> None:
        self.p: P.Params = bundle["params"]
        self.refs = bundle["refs"]
        self.approach = bundle["approach"]
        self.flight = {**bundle["flight"], **FLIGHT_OVERRIDE}
        self.refractory = bundle.get("refractory", {})
        self.single_group = bundle.get("single_group", {})
        self.flat_model = bundle.get("flat_model")
        self.group_model = bundle.get("group_model")
        self.side_models = bundle.get("side_models", {})
        self.side_gates = bundle.get("side_gates", {})
        self.gesture_model = bundle.get("gesture_model")
        self.novelty = bundle.get("novelty")
        self.novelty_limit = bundle.get("novelty_limit", float("inf"))
        self.buffer: deque = deque(maxlen=int(BUFFER_S * FS))
        self.emg_hist: deque = deque(maxlen=int(self.p.history_s * FS / TICK))
        self.gyro_hist: deque = deque(maxlen=int(self.p.history_s * FS / TICK))
        self.eog_hist: deque = deque(maxlen=int(self.p.history_s * FS / TICK))
        self.samples = 0
        self.pending_until: int | None = None
        self.onset_sample = 0
        self.blocked_until = 0
        self.last_z = 0.0

    # -------------------------------------------------------------- stream

    def push(self, chunk: np.ndarray) -> dict | None:
        """Feed new raw samples (n, 17). Returns a decision dict when one is made."""
        for row in chunk:
            self.buffer.append(row)
        self.samples += len(chunk)
        if len(self.buffer) < FS:
            return None

        recent = np.asarray(list(self.buffer)[-FS:])
        emg, gyro, eog = P.raw_activity(recent, self.p)
        n = int(ACTIVITY_S * FS)
        emg_now, gyro_now, eog_now = float(emg[-n:].mean()), float(gyro[-n:].mean()), float(eog[-n:].mean())
        warm = len(self.emg_hist) >= self.emg_hist.maxlen // 4
        if warm:
            z = lambda now, hist: P.robust_z(np.array([now]), np.asarray(hist))[0]
            self.last_z = float(z(emg_now, self.emg_hist) + z(gyro_now, self.gyro_hist))
            if self.p.use_eog:
                self.last_z += float(z(eog_now, self.eog_hist))
        # Only quiet moments feed the baseline, so a long gesture cannot raise it.
        if self.last_z < self.p.onset_z:
            self.emg_hist.append(emg_now)
            self.gyro_hist.append(gyro_now)
            self.eog_hist.append(eog_now)

        loud = gyro_now >= self.p.gyro_floor or emg_now >= self.p.emg_floor
        if self.p.use_eog:
            loud = loud or eog_now >= self.p.eog_floor
        if self.pending_until is None:
            if warm and loud and self.last_z >= self.p.onset_z and self.samples >= self.blocked_until:
                # The peak may land up to PEAK_SEARCH_S after the onset, and the
                # window then needs `post` more seconds after the peak.
                post = max(self.p.epoch_s - self.p.epoch_pre_s, self.p.arm_post_s)
                self.pending_until = self.samples + int((PEAK_SEARCH_S + post + 0.05) * FS)
                self.onset_sample = self.samples
            return None
        if self.samples < self.pending_until:
            return None

        self.pending_until = None
        decision = self._decide()
        # Pause counted from the gesture's onset (not the later decision), using
        # the detected input's own refractory time; the longest one when unsure.
        pause = self.refractory.get(decision.get("label"), self.p.refractory_s)
        self.blocked_until = self.onset_sample + int(pause * FS)
        return decision

    # -------------------------------------------------------------- decision

    def _decide(self) -> dict:
        data = np.asarray(self.buffer)
        # The peak is searched from 0.3 s before to 0.7 s after the detected
        # onset, the same span the training repetitions were anchored on.
        first = self.samples - len(data)                 # stream index of data[0]
        start = max(0, self.onset_sample - int(0.3 * FS) - first)
        stop = min(len(data), self.onset_sample + int(PEAK_SEARCH_S * FS) - first)
        env = P.envelope(*P.raw_activity(data, self.p), params=self.p)
        peak = start + int(np.argmax(env[start:stop]))
        window = P.epoch_at(data, peak, self.p)
        if window is None:
            return {"label": None, "command": None, "reason": "window out of buffer"}

        arm_window = P.arm_epoch_at(data, peak, self.p)
        if arm_window is None:
            return _unsure("window out of buffer")
        x = P.input_features(window, arm_window, self.refs, self.p).reshape(1, -1)

        if self.novelty is not None:
            distance = float(self.novelty.distance(x)[0])
            if distance > self.novelty_limit:
                return _unsure(f"unlike any trained gesture ({distance:.0f} > {self.novelty_limit:.0f})")
        if self.gesture_model is not None:
            what, g_conf = _best(self.gesture_model, x)
            if what != "gesto" or g_conf < self.p.gate_gesture:
                return _unsure(f"other movement (gesture {g_conf if what == 'gesto' else 1 - g_conf:.2f})")

        if self.approach == "flat":
            label, conf = _best(self.flat_model, x)
        else:
            if self.group_model is not None:
                group, g_conf = _best(self.group_model, x)
            else:
                group, g_conf = next(iter(self.side_models)), 1.0
            if group in self.side_models:
                label, s_conf = _best(self.side_models[group], x)
            else:
                label, s_conf = self.single_group.get(group, group), 1.0
            if g_conf < self.p.gate_type:
                return _unsure(f"group {group} {g_conf:.2f} < {self.p.gate_type:.2f}")
            side_gate = self.side_gates.get(group, 0.0)
            if s_conf < side_gate:
                return _unsure(f"{group} side {s_conf:.2f} < {side_gate:.2f}")
            return {"label": label, "command": self.flight.get(label, label), "confidence": min(g_conf, s_conf)}
        if conf < self.p.gate_flat:
            return _unsure(f"{label} {conf:.2f} < {self.p.gate_flat:.2f}")
        return {"label": label, "command": self.flight.get(label, label), "confidence": conf}


def _best(model, x):
    proba = model.predict_proba(x)[0]
    i = int(np.argmax(proba))
    return str(model.classes_[i]), float(proba[i])


def _unsure(reason):
    return {"label": None, "command": None, "reason": reason}


def report(decision: dict, t: float) -> None:
    if decision["command"]:
        print(f"[{t:7.2f}s] {decision['label']:14s} -> {decision['command']:16s} ({decision['confidence']:.2f})")
    else:
        print(f"[{t:7.2f}s] {'UNSURE':14s} -> no command  ({decision['reason']})")


def run_replay(clf: GestureClassifier, path: str, realtime: bool) -> list[dict]:
    data = P.load_csv(path, P.Params(settle_s=0.0))
    decisions = []
    for start in range(0, len(data), TICK):
        decision = clf.push(data[start:start + TICK])
        if decision:
            report(decision, clf.samples / FS)
            decisions.append(decision)
        if realtime:
            time.sleep(TICK / FS)
    return decisions


def run_lsl(clf: GestureClassifier, stream: str) -> None:
    from pylsl import StreamInlet, resolve_byprop

    found = resolve_byprop("name", stream, timeout=8.0)
    if not found:
        raise SystemExit(f"No LSL stream '{stream}'")
    info = found[0]
    if info.channel_count() < MIN_CHANNELS:
        raise SystemExit(
            f"'{stream}' has {info.channel_count()} channels; need at least {MIN_CHANNELS} "
            "(8 EEG + accelerometer + gyroscope). Enable raw data output in Unicorn Recorder."
        )
    if abs(info.nominal_srate() - FS) > 1:
        raise SystemExit(f"'{stream}' runs at {info.nominal_srate():.0f} Hz; the models were trained at {FS} Hz.")
    inlet = StreamInlet(info, max_buflen=4)
    print(f"Connected to '{stream}'. Stay still ~5 s while the baseline fills, then gesture.")
    started = time.monotonic()
    try:
        while True:
            samples, _ = inlet.pull_chunk(timeout=0.05, max_samples=TICK * 4)
            if not samples:
                continue
            decision = clf.push(np.asarray(samples, dtype=float))
            if decision:
                report(decision, time.monotonic() - started)
    except KeyboardInterrupt:
        print("\nStopped.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Unicorn LSL -> gesture -> flight function")
    ap.add_argument("--model", default=os.path.join(HERE, "models", "brazos.joblib"),
                    help="A model made by train.py (path, or a preset name like 'cabeza')")
    ap.add_argument("--stream", default=STREAM_NAME)
    ap.add_argument("--replay", help="Feed a recorded CSV instead of LSL")
    ap.add_argument("--realtime", action="store_true", help="With --replay, play at real speed")
    args = ap.parse_args()

    path = args.model
    if not os.path.exists(path) and os.path.exists(os.path.join(HERE, "models", f"{path}.joblib")):
        path = os.path.join(HERE, "models", f"{path}.joblib")
    bundle = joblib.load(path)
    clf = GestureClassifier(bundle)
    print("Active inputs: " + ", ".join(f"{name} -> {cmd}" for name, cmd in clf.flight.items()))
    if args.replay:
        run_replay(clf, args.replay, args.realtime)
    else:
        run_lsl(clf, args.stream)


if __name__ == "__main__":
    main()
