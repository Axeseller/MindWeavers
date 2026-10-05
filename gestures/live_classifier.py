"""Live gesture -> flight command, from the Unicorn raw LSL stream.

    python live_classifier.py                                   # live LSL
    python live_classifier.py --replay recording.csv            # feed a CSV as if it were live

Prints one line per decision. It never talks to the drone: it only names the
flight function, so it can be wired into the app later.

How a decision is made
  1. Activity level (EMG 30-100 Hz + gyro) is tracked against a rolling 20 s
     median/MAD. A gesture starts when it crosses `onset_z` AND beats the
     absolute floor measured on the rest recording.
  2. ~1.3 s later the windows around the activity peak are cut out (1 s for
     arm/fist and fist side; 1.5 s for arm side, which needs the movement shape).
  3. Stage B decides arm vs fist; stage C decides left vs right.
  4. A window unlike every trained gesture (novelty distance) is rejected first.
     If any stage is below its confidence gate the answer is UNSURE and no
     command is emitted. Then nothing is accepted for `refractory_s`.
"""

from __future__ import annotations

import argparse
import time
from collections import deque

import joblib
import numpy as np

import pipeline as P

FS = P.FS
STREAM_NAME = "UnicornRecorderRawDataLSLStream"
TICK = 10                      # samples per update (40 ms)
BUFFER_S = 4.0                 # raw samples kept
ACTIVITY_S = 0.1               # level = mean activity of the newest 100 ms

#: Gesture -> flight function. Edit here; the classifier does not care.
FLIGHT = {
    "puno_izq": "GIRAR_IZQUIERDA",
    "puno_der": "GIRAR_DERECHA",
    "brazo_der": "SUBIR",
    "brazo_izq": "BAJAR",
}


class GestureClassifier:
    def __init__(self, bundle: dict) -> None:
        self.p: P.Params = bundle["params"]
        self.refs = bundle["refs"]
        self.type_model = bundle["type_model"]
        self.puno_model = bundle["puno_model"]
        self.brazo_model = bundle["brazo_model"]
        self.novelty = bundle.get("novelty")
        self.novelty_limit = bundle.get("novelty_limit", float("inf"))
        self.buffer: deque = deque(maxlen=int(BUFFER_S * FS))
        self.emg_hist: deque = deque(maxlen=int(self.p.history_s * FS / TICK))
        self.gyro_hist: deque = deque(maxlen=int(self.p.history_s * FS / TICK))
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
        emg, gyro = P.raw_activity(recent, self.p)
        n = int(ACTIVITY_S * FS)
        emg_now, gyro_now = float(emg[-n:].mean()), float(gyro[-n:].mean())
        warm = len(self.emg_hist) >= self.emg_hist.maxlen // 4
        if warm:
            self.last_z = float(
                P.robust_z(np.array([emg_now]), np.asarray(self.emg_hist))[0]
                + P.robust_z(np.array([gyro_now]), np.asarray(self.gyro_hist))[0]
            )
        # Only quiet moments feed the baseline, so a long gesture cannot raise it.
        if self.last_z < self.p.onset_z:
            self.emg_hist.append(emg_now)
            self.gyro_hist.append(gyro_now)

        loud = gyro_now >= self.p.gyro_floor or emg_now >= self.p.emg_floor
        if self.pending_until is None:
            if warm and loud and self.last_z >= self.p.onset_z and self.samples >= self.blocked_until:
                post = max(self.p.epoch_s - self.p.epoch_pre_s, self.p.arm_post_s)
                self.pending_until = self.samples + int((post + 0.3) * FS)
                self.onset_sample = self.samples
            return None
        if self.samples < self.pending_until:
            return None

        self.pending_until = None
        self.blocked_until = self.samples + int(self.p.refractory_s * FS)
        return self._decide()

    # -------------------------------------------------------------- decision

    def _decide(self) -> dict:
        data = np.asarray(self.buffer)
        # The peak is searched from 0.3 s before to 0.7 s after the detected
        # onset, the same span the training repetitions were anchored on.
        first = self.samples - len(data)                 # stream index of data[0]
        start = max(0, self.onset_sample - int(0.3 * FS) - first)
        stop = min(len(data), self.onset_sample + int(0.7 * FS) - first)
        env = P.envelope(*P.raw_activity(data, self.p))
        peak = start + int(np.argmax(env[start:stop]))
        window = P.epoch_at(data, peak, self.p)
        if window is None:
            return {"label": None, "command": None, "reason": "window out of buffer"}

        full = P.full_features(window, self.refs, self.p).reshape(1, -1)
        if self.novelty is not None:
            distance = float(self.novelty.distance(full)[0])
            if distance > self.novelty_limit:
                return _unsure(f"unlike any trained gesture ({distance:.0f} > {self.novelty_limit:.0f})")
        kind, k_conf = _best(self.type_model, full)
        if k_conf < self.p.gate_type:
            return _unsure(f"arm/fist {k_conf:.2f} < {self.p.gate_type:.2f}")

        if kind == "puno":
            side, s_conf = _best(self.puno_model, full)
            gate = self.p.gate_puno
        else:
            arm_window = P.arm_epoch_at(data, peak, self.p)
            if arm_window is None:
                return _unsure("arm window out of buffer")
            side, s_conf = _best(self.brazo_model, P.arm_side_features(arm_window, self.p).reshape(1, -1))
            gate = self.p.gate_brazo
        if s_conf < gate:
            return _unsure(f"{kind} side {s_conf:.2f} < {gate:.2f}")

        label = f"{kind}_{side}"
        return {"label": label, "command": FLIGHT[label], "confidence": min(k_conf, s_conf)}


def _best(model, x):
    proba = model.predict_proba(x)[0]
    i = int(np.argmax(proba))
    return str(model.classes_[i]), float(proba[i])


def _unsure(reason):
    return {"label": None, "command": None, "reason": reason}


def report(decision: dict, t: float) -> None:
    if decision["command"]:
        print(f"[{t:7.2f}s] {decision['label']:10s} -> {decision['command']:16s} ({decision['confidence']:.2f})")
    else:
        print(f"[{t:7.2f}s] UNSURE     -> no command  ({decision['reason']})")


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
    inlet = StreamInlet(found[0], max_buflen=4)
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
    ap = argparse.ArgumentParser(description="Unicorn LSL -> fist/arm gesture -> flight function")
    ap.add_argument("--model", default="gesture_model.joblib")
    ap.add_argument("--stream", default=STREAM_NAME)
    ap.add_argument("--replay", help="Feed a recorded CSV instead of LSL")
    ap.add_argument("--realtime", action="store_true", help="With --replay, play at real speed")
    args = ap.parse_args()

    clf = GestureClassifier(joblib.load(args.model))
    if args.replay:
        run_replay(clf, args.replay, args.realtime)
    else:
        run_lsl(clf, args.stream)


if __name__ == "__main__":
    main()
