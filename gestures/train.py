"""Train the staged gesture classifier and pick each stage's confidence gate.

    python train.py --data <folder with the baseline CSVs>

Validation: every recording is cut into 5 time blocks and a block is never in
training and testing at once (GroupKFold), so neighbouring repetitions cannot
leak into the score. Each gate is the highest threshold whose validated error is
0 % while still answering >= 80 %; if none reaches 0 %, the lowest error.
"""

from __future__ import annotations

import argparse
import glob
import os
import warnings

import joblib
import numpy as np
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold, cross_val_predict
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import pipeline as P

warnings.filterwarnings("ignore")

FILE_PATTERNS = {
    "puno_izq": "pu*oizquierdo*",
    "puno_der": "pu*oderecho*",
    "brazo_izq": "brazoizquierdo*",
    "brazo_der": "brazoarriba*",   # assumed: "brazo arriba" = right arm
}
REST_PATTERN = "rest_*"
GATES = (0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 0.98, 0.99)


def set_floors(folder, params):
    """Absolute onset floors = 110 % of the loudest 100 ms in the rest recording.

    The first 10 s of that recording are skipped: in the team's rest file someone
    adjusts the cap at 5-10 s (gyro up to ~90 deg/s), which is not rest.
    """
    for path in sorted(glob.glob(os.path.join(folder, REST_PATTERN + ".csv")), key=os.path.getsize, reverse=True):
        data = P.load_csv(path, params)[5 * P.FS:]
        if len(data) < 10 * P.FS:
            continue
        emg, gyro = P.raw_activity(data, params)
        kernel = np.ones(25) / 25
        params.emg_floor = float(np.convolve(emg, kernel, "same").max() * 1.1)
        params.gyro_floor = float(np.convolve(gyro, kernel, "same").max() * 1.1)
        print(f"  onset floors from {os.path.basename(path)}: emg {params.emg_floor:.2f}, gyro {params.gyro_floor:.2f}")
        return
    print("  [!] no rest recording found; using default onset floors")


def novelty_threshold(X, groups):
    """99th percentile of distances for windows held out of the fit (no leakage)."""
    held = []
    for block in np.unique(groups):
        train, test = groups != block, groups == block
        held.extend(P.Novelty(X[train]).distance(X[test]))
    return float(np.percentile(held, 99))


def lda():
    return make_pipeline(StandardScaler(), LinearDiscriminantAnalysis(solver="lsqr", shrinkage="auto"))


def logreg():
    return make_pipeline(StandardScaler(), LogisticRegression(C=0.3, max_iter=5000))


def collect(folder, params):
    windows, arm_windows, labels, blocks = [], [], [], []
    for label, pattern in FILE_PATTERNS.items():
        hits = sorted(glob.glob(os.path.join(folder, pattern + ".csv")))
        if not hits:
            raise SystemExit(f"Missing recording for '{label}' ({pattern}.csv)")
        data = P.load_csv(hits[-1], params)
        peaks = P.find_repetitions(data, params)
        n = 0
        for peak in peaks:
            win = P.epoch_at(data, peak, params)
            arm_win = P.arm_epoch_at(data, peak, params)
            if win is not None and arm_win is not None:
                windows.append(win)
                arm_windows.append(arm_win)
                labels.append(label)
                blocks.append(min(4, peak * 5 // len(data)))
                n += 1
        print(f"  {label:10s} {n:3d} repetitions  <- {os.path.basename(hits[-1])}")
    return windows, arm_windows, np.asarray(labels), np.asarray(blocks)


def validate(name, make, X, y, groups):
    proba = cross_val_predict(make(), X, y, groups=groups, cv=GroupKFold(5), method="predict_proba")
    classes = np.unique(y)
    pred, conf = classes[proba.argmax(axis=1)], proba.max(axis=1)
    print(f"\n[{name}] accuracy {(pred == y).mean() * 100:.1f}%  (n={len(y)}, chance {100 / len(classes):.0f}%)")
    print("   gate   answered   error")
    rows = []
    for t in GATES:
        kept = conf >= t
        if kept.any():
            err = (pred[kept] != y[kept]).mean()
            rows.append((t, kept.mean(), err))
            print(f"   {t:4.2f}   {kept.mean() * 100:5.1f}%    {err * 100:5.1f}%")
    # Safety margin: among thresholds with 0 % validated error that still answer
    # at least 80 % of gestures, take the HIGHEST. Otherwise the lowest error.
    zero = [r for r in rows if r[2] == 0.0 and r[1] >= 0.8]
    usable = [r for r in rows if r[1] >= 0.8] or rows
    best = zero[-1] if zero else min(usable, key=lambda r: (r[2], -r[1]))
    print(f"   -> gate {best[0]:.2f}: answers {best[1] * 100:.0f}%, error {best[2] * 100:.1f}%")
    return best[0], best, rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", default="gesture_model.joblib")
    args = ap.parse_args()

    params = P.Params()
    set_floors(args.data, params)
    windows, arm_windows, labels, blocks = collect(args.data, params)
    refs = P.tangent_reference(windows, params)
    full = np.asarray([P.full_features(w, refs, params) for w in windows])
    arm = np.asarray([P.arm_side_features(w, params) for w in arm_windows])

    kind = np.where(np.char.startswith(labels, "brazo"), "brazo", "puno")
    side = np.where(np.char.endswith(labels, "izq"), "izq", "der")
    is_puno, is_brazo = kind == "puno", kind == "brazo"

    params.gate_type, b1, _ = validate("B  brazo vs puño", lda, full, kind, blocks)
    params.gate_puno, b2, _ = validate("C1 puño izq vs der", lda, full[is_puno], side[is_puno], blocks[is_puno])

    # Arm side: LDA tends to be over-confident on these features (it says 100 %
    # even when wrong, so no gate can filter its mistakes). Let validation pick.
    arm_candidates = {}
    for name, make in (("lda", lda), ("logreg", logreg)):
        gate, best, _ = validate(f"C2 brazo izq vs der [{name}]", make, arm[is_brazo], side[is_brazo], blocks[is_brazo])
        arm_candidates[name] = (best[2], -best[1], gate, best, make)
    arm_name = min(arm_candidates, key=lambda k: arm_candidates[k][:2])
    _, _, params.gate_brazo, b3, arm_make = arm_candidates[arm_name]
    print(f"   -> arm side uses {arm_name}")

    print("\nEnd to end (stage B gate x stage C gate), per gesture type:")
    for name, c in (("puño", b2), ("brazo", b3)):
        answered = b1[1] * c[1]
        correct = (1 - b1[2]) * (1 - c[2])
        print(f"   {name:6s} answers {answered * 100:4.0f}% of gestures, wrong on {(1 - correct) * 100:4.1f}% of those")

    novelty_limit = novelty_threshold(full, blocks)
    print(f"\nNovelty limit (99th pct of held-out distances): {novelty_limit:.1f}")

    bundle = {
        "novelty": P.Novelty(full),
        "novelty_limit": novelty_limit,
        "params": params,
        "refs": refs,
        "type_model": lda().fit(full, kind),
        "puno_model": lda().fit(full[is_puno], side[is_puno]),
        "brazo_model": arm_make().fit(arm[is_brazo], side[is_brazo]),
    }
    joblib.dump(bundle, args.out)
    print(f"\nSaved {args.out}")


if __name__ == "__main__":
    main()
