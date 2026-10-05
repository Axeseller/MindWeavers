"""Replay the recordings of a model's inputs (plus rest) through live_classifier.py.

    python evaluate_replay.py <csv folder> models/brazos.joblib
"""
import contextlib
import glob
import io
import os
import sys
import warnings
from collections import Counter

import joblib

from live_classifier import GestureClassifier, run_replay

warnings.filterwarnings("ignore")
folder, model_path = sys.argv[1], sys.argv[2]
bundle = joblib.load(model_path)
recordings = {spec["name"]: spec["recording"] for spec in bundle["inputs"]}
recordings["reposo"] = "rest_20261004_141750"
total = Counter()
for label, pattern in recordings.items():
    clf = GestureClassifier(bundle)
    with contextlib.redirect_stdout(io.StringIO()):
        decisions = run_replay(clf, glob.glob(os.path.join(folder, pattern + ".csv"))[0], False)
    counts = Counter(d["label"] or "UNSURE" for d in decisions)
    right = counts.get(label, 0)
    wrong = sum(v for k, v in counts.items() if k not in (label, "UNSURE"))
    total.update(right=right, wrong=wrong, unsure=counts.get("UNSURE", 0))
    print(f"{label:14s} correct {right:3d}  WRONG {wrong:3d}  unsure {counts.get('UNSURE', 0):3d}   {dict(counts)}")
print(f"{'TOTAL':14s} correct {total['right']:3d}  WRONG {total['wrong']:3d}  unsure {total['unsure']:3d}")
