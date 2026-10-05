import sys, glob, os, warnings, joblib
from collections import Counter
warnings.filterwarnings("ignore")
import io, contextlib
from live_classifier import GestureClassifier, run_replay
B=sys.argv[1]
for name,pat in (("puno_izq","pu*oizquierdo*"),("puno_der","pu*oderecho*"),("brazo_izq","brazoizquierdo*"),("brazo_der","brazoarriba*"),("rest","rest_20261004_141750")):
    clf=GestureClassifier(joblib.load("gesture_model.joblib"))
    with contextlib.redirect_stdout(io.StringIO()):
        d=run_replay(clf, glob.glob(os.path.join(B,pat+".csv"))[0], False)
    c=Counter(x["label"] or "UNSURE" for x in d)
    print(f"{name:10s} decisions {len(d):3d}  {dict(c)}")
