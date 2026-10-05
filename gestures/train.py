"""Train a model for the inputs you choose (one file per input in inputs/).

    python train.py --data <csv folder> --preset brazos
    python train.py --data <csv folder> --inputs puno_izq,puno_der,blink,happy
    python train.py --list

The model is trained on exactly the active inputs. It compares two designs and
keeps whichever validates with fewer mistakes:

  flat     one classifier over all active inputs
  grouped  first the group (puño / brazo / cuello ...), then left vs right
           inside groups that have a pair

Before either, stage A rejects movements that are not a trained gesture
(turning back to centre, lowering an arm, releasing a fist).

Validation: each recording is cut into 5 time blocks and a block is never in
training and testing at once, so neighbouring repetitions cannot leak into the
score. The confidence gate is the highest one with 0 % validated error that
still answers >= 80 % of gestures; if none reaches 0 %, the lowest error.
"""

from __future__ import annotations

import argparse
import glob
import os
import warnings

import joblib
import numpy as np
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.metrics import confusion_matrix
from sklearn.model_selection import GroupKFold, cross_val_predict
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import inputs as I
import pipeline as P

warnings.filterwarnings("ignore")

REST_PATTERN = "rest_*"
GATES = (0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 0.98, 0.99)
COLLISION = 0.10        # warn when two inputs are confused this often
MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")


def lda():
    return make_pipeline(StandardScaler(), LinearDiscriminantAnalysis(solver="lsqr", shrinkage="auto"))


# ------------------------------------------------------------------ data

def set_floors(folder, params):
    """Absolute onset floors = 110 % of the loudest 100 ms in the rest recording.

    The first 10 s of that recording are skipped: in the team's rest file someone
    adjusts the cap at 5-10 s (gyro up to ~90 deg/s), which is not rest.
    """
    for path in sorted(glob.glob(os.path.join(folder, REST_PATTERN + ".csv")), key=os.path.getsize, reverse=True):
        data = P.load_csv(path, params)[5 * P.FS:]
        if len(data) < 10 * P.FS:
            continue
        emg, gyro, eog = P.raw_activity(data, params)
        kernel = np.ones(25) / 25
        params.emg_floor = float(np.convolve(emg, kernel, "same").max() * 1.1)
        params.gyro_floor = float(np.convolve(gyro, kernel, "same").max() * 1.1)
        if params.use_eog:
            params.eog_floor = float(np.convolve(eog, kernel, "same").max() * 1.1)
        print(f"  onset floors from {os.path.basename(path)}: emg {params.emg_floor:.2f}, "
              f"gyro {params.gyro_floor:.2f}, eog {params.eog_floor:.2f}")
        return
    print("  [!] no rest recording found; using default onset floors")


def collect(folder, params, specs):
    """Gesture windows per input, plus 'other movement' windows from every recording."""
    pairs, labels, blocks, other_pairs, other_blocks = [], [], [], [], []
    for spec in specs:
        hits = sorted(glob.glob(os.path.join(folder, spec.recording + ".csv")))
        if not hits:
            raise SystemExit(f"Missing recording for '{spec.name}' ({spec.recording}.csv)")
        data = P.load_csv(hits[-1], params)
        peaks = P.find_repetitions(data, params)
        n = 0
        for peak in peaks:
            win, arm = P.epoch_at(data, peak, params), P.arm_epoch_at(data, peak, params)
            if win is not None and arm is not None:
                pairs.append((win, arm))
                labels.append(spec.name)
                blocks.append(min(4, peak * 5 // len(data)))
                n += 1
        for other in P.find_other_movements(data, peaks, params):
            win, arm = P.epoch_at(data, other, params), P.arm_epoch_at(data, other, params)
            if win is not None and arm is not None:
                other_pairs.append((win, arm))
                other_blocks.append(min(4, other * 5 // len(data)))
        print(f"  {spec.name:14s} {n:3d} repetitions  <- {os.path.basename(hits[-1])}")
    print(f"  {'otro':14s} {len(other_pairs):3d} non-gesture movements (returns, releases)")
    return pairs, np.asarray(labels), np.asarray(blocks), other_pairs, np.asarray(other_blocks)


# ------------------------------------------------------------------ validation

def pick_gate(name, y, pred, conf):
    print(f"\n[{name}] accuracy {(pred == y).mean() * 100:.1f}%  (n={len(y)}, chance {100 / len(np.unique(y)):.0f}%)")
    print("   gate   answered   error")
    rows = []
    for t in GATES:
        kept = conf >= t
        if kept.any():
            err = (pred[kept] != y[kept]).mean()
            rows.append((t, kept.mean(), err))
            print(f"   {t:4.2f}   {kept.mean() * 100:5.1f}%    {err * 100:5.1f}%")
    zero = [r for r in rows if r[2] == 0.0 and r[1] >= 0.8]
    usable = [r for r in rows if r[1] >= 0.8] or rows
    best = zero[-1] if zero else min(usable, key=lambda r: (r[2], -r[1]))
    print(f"   -> gate {best[0]:.2f}: answers {best[1] * 100:.0f}%, error {best[2] * 100:.1f}%")
    return best


def cv_flat(X, y, blocks):
    proba = cross_val_predict(lda(), X, y, groups=blocks, cv=GroupKFold(5), method="predict_proba")
    classes = np.unique(y)
    return classes[proba.argmax(axis=1)], proba.max(axis=1)


def fit_block(X, y, blocks, cols, choose=False, groups_cv=None):
    """Fit LDA on one block, or (choose=True) on whichever block validates best."""
    options = [cols["full"], cols["movement"], cols["all"]] if choose else [cols["full"]]
    best, best_acc = options[0], -1.0
    if choose and groups_cv is not None and len(np.unique(groups_cv)) >= 3:
        for c in options:
            n = min(5, len(np.unique(groups_cv)))
            pred = cross_val_predict(lda(), X[:, c[0]:c[1]], y, groups=groups_cv, cv=GroupKFold(n))
            acc = (pred == y).mean()
            if acc > best_acc:
                best, best_acc = c, acc
    return P.Block(lda().fit(X[:, best[0]:best[1]], y), best)


def fit_grouped(X, y, group_of, blocks, cols):
    """Group stage on the 'full' block; each left/right pair picks its own block."""
    groups = np.array([group_of[label] for label in y])
    group_model = fit_block(X, groups, blocks, cols) if len(np.unique(groups)) > 1 else None
    side_models = {}
    for group in np.unique(groups):
        inside = groups == group
        if len(np.unique(y[inside])) > 1:
            side_models[group] = fit_block(X[inside], y[inside], blocks, cols, choose=True, groups_cv=blocks[inside])
    return group_model, side_models


def predict_grouped(group_model, side_models, X, single):
    """Label, group confidence and side confidence for each row."""
    out = []
    for x in X:
        if group_model is not None:
            proba = group_model.predict_proba(x)[0]
            group, g_conf = str(group_model.classes_[proba.argmax()]), float(proba.max())
        else:
            group, g_conf = next(iter(side_models)), 1.0
        if group in side_models:
            proba = side_models[group].predict_proba(x)[0]
            label, s_conf = str(side_models[group].classes_[proba.argmax()]), float(proba.max())
        else:
            label, s_conf = single.get(group, group), 1.0
        out.append((label, g_conf, s_conf))
    return out


def cv_grouped(X, y, blocks, group_of, single, cols):
    rows = [None] * len(y)
    for train, test in GroupKFold(5).split(X, y, blocks):
        group_model, side_models = fit_grouped(X[train], y[train], group_of, blocks[train], cols)
        for i, r in zip(test, predict_grouped(group_model, side_models, X[test], single)):
            rows[i] = r
    labels = np.array([r[0] for r in rows])
    return labels, np.array([r[1] for r in rows]), np.array([r[2] for r in rows])


def _rule(rows):
    """Highest gate with 0 % error that still answers >= 80 %; else the lowest error."""
    zero = [r for r in rows if r[2] == 0.0 and r[1] >= 0.8]
    usable = [r for r in rows if r[1] >= 0.8] or rows
    return zero[-1] if zero else min(usable, key=lambda r: (r[2], -r[1]))


def pick_grouped_gates(name, y, pred, g_conf, s_conf, group_of):
    """One gate for the group stage, and one gate PER left/right pair."""
    print(f"\n[{name}] accuracy {(pred == y).mean() * 100:.1f}%  (n={len(y)})")
    truth_group = np.array([group_of[label] for label in y])
    pred_group = np.array([group_of.get(label, label) for label in pred])
    side_gates = {}
    for group in np.unique(truth_group):
        # Judge the side stage only where the group stage was right; routing
        # mistakes belong to the group gate, not to this pair's gate.
        inside = (truth_group == group) & (pred_group == group) & (s_conf < 1.0)
        if not inside.any():
            continue
        rows = []
        for sg in GATES:
            kept = inside & (s_conf >= sg)
            if kept.any():
                rows.append((sg, kept.sum() / inside.sum(), (pred[kept] != y[kept]).mean()))
        best = _rule(rows)
        side_gates[group] = best[0]
        print(f"   pair {group:10s} side gate {best[0]:.2f}: answers {best[1] * 100:.0f}%, error {best[2] * 100:.1f}%")
    side_ok = np.array([s_conf[i] >= side_gates.get(truth_group[i], 0.0) for i in range(len(y))])
    rows = []
    for gg in GATES:
        kept = side_ok & (g_conf >= gg)
        if kept.any():
            rows.append((gg, kept.mean(), (pred[kept] != y[kept]).mean()))
    best = _rule(rows)
    print(f"   -> group gate {best[0]:.2f}: answers {best[1] * 100:.0f}% overall, error {best[2] * 100:.1f}%")
    return best, side_gates


def report_collisions(y, pred):
    classes = np.unique(y)
    matrix = confusion_matrix(y, pred, labels=classes)
    found = False
    for i, a in enumerate(classes):
        for j, b in enumerate(classes):
            if i != j and matrix[i].sum() and matrix[i, j] / matrix[i].sum() >= COLLISION:
                if not found:
                    print("\n[!] Inputs that collide (do not activate both if you can avoid it):")
                    found = True
                print(f"    {a} read as {b} in {matrix[i, j]}/{matrix[i].sum()} validated repetitions")
    if not found:
        print("\nNo colliding inputs in this selection.")


def novelty_threshold(X, groups):
    """99th percentile of distances for windows held out of the fit (no leakage)."""
    held = []
    for block in np.unique(groups):
        train, test = groups != block, groups == block
        held.extend(P.Novelty(X[train]).distance(X[test]))
    return float(np.percentile(held, 99))


# ------------------------------------------------------------------ main

def main():
    ap = argparse.ArgumentParser(description="Train a model for the chosen inputs")
    ap.add_argument("--data", help="Folder with the recording CSVs")
    ap.add_argument("--preset", choices=sorted(I.PRESETS))
    ap.add_argument("--inputs", help="Comma-separated input names (see --list)")
    ap.add_argument("--out", help="Model path (default: models/<preset or inputs>.joblib)")
    ap.add_argument("--list", action="store_true", help="Show available inputs and presets")
    args = ap.parse_args()

    if args.list:
        for name in I.available():
            spec = I.load(name)
            print(f"  {spec.name:14s} -> {spec.flight:16s} group {spec.group}")
        for preset, names in I.PRESETS.items():
            print(f"  preset {preset:7s}: {', '.join(names)}")
        return
    if not args.data or not (args.preset or args.inputs):
        raise SystemExit("Give --data and either --preset or --inputs (or use --list).")

    names = I.PRESETS[args.preset] if args.preset else [n.strip() for n in args.inputs.split(",") if n.strip()]
    unknown = sorted(set(names) - set(I.available()))
    if unknown:
        raise SystemExit(f"Unknown inputs: {unknown}. Available: {I.available()}")
    if len(names) < 2:
        raise SystemExit("Choose at least two inputs.")
    specs = [I.load(n) for n in names]
    tag = args.preset or "_".join(names)
    out = args.out or os.path.join(MODEL_DIR, f"{tag}.joblib")

    params = P.Params(use_eog=any(s.uses_eyes for s in specs))
    params.refractory_s = max(s.refractory_s for s in specs)
    print(f"Inputs: {', '.join(names)}  (eyes {'on' if params.use_eog else 'off'})")
    set_floors(args.data, params)
    pairs, y, blocks, other_pairs, other_blocks = collect(args.data, params, specs)

    refs = P.tangent_reference([w for w, _ in pairs], params)
    X = np.asarray([P.input_features(w, a, refs, params) for w, a in pairs])
    cols = P.feature_blocks(pairs[0][0], pairs[0][1], refs, params)
    XO = np.asarray([P.input_features(w, a, refs, params) for w, a in other_pairs])

    # Stage A: trained gesture, or some other movement?
    a_X = np.vstack([X, XO])
    a_y = np.r_[np.full(len(X), "gesto"), np.full(len(XO), "otro")]
    a_g = np.r_[blocks, other_blocks]
    a_pred, a_conf = cv_flat(a_X, a_y, a_g)
    params.gate_gesture = pick_gate("A  gesto vs otro movimiento", a_y, a_pred, a_conf)[0]

    # Gesture stage: flat vs grouped, keep the one with fewer validated mistakes.
    group_of = {s.name: s.group for s in specs}
    single = {s.group: s.name for s in specs if sum(t.group == s.group for t in specs) == 1}
    flat_pred, flat_conf = cv_flat(X, y, blocks)
    flat_best = pick_gate("gestos — una etapa", y, flat_pred, flat_conf)
    candidates = {"flat": (flat_best, flat_pred)}
    if len(set(group_of.values())) < len(specs):
        grp_pred, g_conf, s_conf = cv_grouped(X, y, blocks, group_of, single, cols)
        grouped_best, side_gates = pick_grouped_gates("gestos — por grupo, luego izq/der", y, grp_pred, g_conf, s_conf, group_of)
        candidates["grouped"] = (grouped_best, grp_pred)
    approach = min(candidates, key=lambda k: (candidates[k][0][2], -candidates[k][0][1]))
    best, pred = candidates[approach]
    side_gate_map = {}
    if approach == "grouped":
        params.gate_type = best[0]
        side_gate_map = side_gates
    else:
        params.gate_flat = best[0]
    print(f"\n-> uses '{approach}': answers {best[1] * 100:.0f}% of gestures, error {best[2] * 100:.1f}%")
    report_collisions(y, pred)

    novelty_limit = novelty_threshold(X, blocks)
    bundle = {
        "inputs": [s.__dict__ for s in specs],
        "flight": {s.name: s.flight for s in specs},
        "refractory": {s.name: s.refractory_s for s in specs},
        "approach": approach,
        "params": params,
        "refs": refs,
        "gesture_model": lda().fit(a_X, a_y),
        "novelty": P.Novelty(X),
        "novelty_limit": novelty_limit,
        "single_group": single,
        "side_gates": side_gate_map,
    }
    if approach == "flat":
        bundle["flat_model"] = lda().fit(X, y)
    else:
        bundle["group_model"], bundle["side_models"] = fit_grouped(X, y, group_of, blocks, cols)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    joblib.dump(bundle, out)
    print(f"\nSaved {out}")


if __name__ == "__main__":
    main()
