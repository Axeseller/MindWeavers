"""Gesture pipeline for the Unicorn Hybrid Black: left/right fist, left/right arm up.

Shared by train.py (offline) and live_classifier.py (LSL), so the numbers computed
in training are exactly the numbers computed in flight.

    raw 17-ch stream
      -> clean      drop settling, remove DC, common-average reference, 60 Hz notch
      -> envelope   z(EMG 30-100 Hz) + z(gyro magnitude): "is something happening?"
      -> epoch      1 s window anchored on the activity peak (0.3 s before, 0.7 s after)
      -> features   band power x channel, C3/C4 + Fz/Oz asymmetry, IMU summary,
                    channel-covariance (tangent space) in 8-30 and 30-100 Hz
      -> stages     A onset   envelope crosses onset_z            (no model)
                    B type    arm vs fist                         (LDA)
                    C side    left vs right, one model per type   (LDA / logistic)
      -> gates      each stage answers only above its own confidence threshold;
                    otherwise the result is "unsure" and no command is sent
"""

from __future__ import annotations

import csv
from dataclasses import dataclass

import numpy as np
from scipy import linalg, signal
from sklearn.covariance import LedoitWolf
from sklearn.preprocessing import StandardScaler

FS = 250
EEG = slice(0, 8)
ACC = slice(8, 11)
GYR = slice(11, 14)
CHANNELS = ("Fz", "C3", "Cz", "C4", "Pz", "PO7", "Oz", "PO8")
GESTURES = ("puno_izq", "puno_der", "brazo_izq", "brazo_der")


@dataclass
class Params:
    settle_s: float = 5.0          # first seconds of each recording: electrodes still settling
    notch_hz: float = 60.0
    epoch_s: float = 1.0           # validated: 1.0 s beat 1.5 s and 2.0 s
    epoch_pre_s: float = 0.3       # window starts this long before the activity peak
    min_gap_s: float = 2.2         # repetitions were ~3 s apart
    # Arm left/right uses its own, longer window: the arm movement outlasts the
    # 1 s epoch, and the SHAPE of it is what separates left from right.
    arm_pre_s: float = 0.5
    arm_post_s: float = 1.0
    wave_points: int = 12          # samples per IMU axis kept from the movement shape
    peak_z: float = 1.0            # offline: peak height (robust SDs) to count as a repetition
    bands: tuple = ((4, 8), (8, 13), (13, 30), (30, 60), (60, 100))
    cov_bands: tuple = ((8, 30), (30, 100))
    # Live
    onset_z: float = 2.5           # envelope level that starts a gesture (relative)
    # Absolute floors: a relative z-score alone fires on tiny wobbles when the
    # baseline is very quiet. Activity must ALSO beat the loudest resting level.
    # train.py measures these on the rest recording; these are the fallbacks.
    gyro_floor: float = 3.0        # deg/s, 100 ms mean
    emg_floor: float = 1.3         # uV, 100 ms mean, 30-100 Hz after CAR
    # Eye activity (frontal EOG, 0.5-8 Hz at Fz). Blinks barely move the gyro or
    # the 30-100 Hz band, so sets that include blinks must also listen to the eyes.
    use_eog: bool = False
    eog_floor: float = float("inf")
    refractory_s: float = 1.5      # no new gesture this soon after a decision
    history_s: float = 20.0        # rolling window for the envelope's median/MAD
    # Confidence gates. train.py overwrites them from validation; these are fallbacks.
    gate_type: float = 0.95        # grouped design: group stage (e.g. puño vs brazo)
    gate_flat: float = 0.95        # flat design: the single gesture stage
    gate_gesture: float = 0.5      # stage A: trained gesture vs other movement


# ------------------------------------------------------------------ io

def load_csv(path: str, params: Params = Params()) -> np.ndarray:
    """record_baseline.py CSV -> (samples, 17). Windows encoding (ñ) tolerated."""
    with open(path, newline="", encoding="latin-1") as handle:
        reader = csv.reader(handle)
        next(reader)
        data = np.asarray([row[1:18] for row in reader], dtype=float)
    return data[int(params.settle_s * FS):]


# ------------------------------------------------------------------ cleaning

def bandpass_sos(lo, hi, order=4):
    return signal.butter(order, [lo / (FS / 2), hi / (FS / 2)], btype="bandpass", output="sos")


def clean_eeg(eeg: np.ndarray, params: Params = Params()) -> np.ndarray:
    eeg = eeg - eeg.mean(axis=0)
    eeg = eeg - eeg.mean(axis=1, keepdims=True)
    b, a = signal.iirnotch(params.notch_hz, 30.0, FS)
    return signal.filtfilt(b, a, eeg, axis=0)


# ------------------------------------------------------------------ envelope

def raw_activity(data: np.ndarray, params: Params = Params()):
    """Per-sample activity before normalisation: EMG power, gyro magnitude, frontal EOG."""
    eeg = clean_eeg(data[:, EEG], params)
    emg = np.sqrt((signal.sosfiltfilt(bandpass_sos(30, 100), eeg, axis=0) ** 2).mean(axis=1))
    gyr = data[:, GYR]
    gyro = np.linalg.norm(gyr - np.median(gyr, axis=0), axis=1)
    eog = np.abs(signal.sosfiltfilt(bandpass_sos(0.5, 8, order=2), eeg[:, 0]))
    return emg, gyro, eog


def robust_z(x, ref=None):
    ref = x if ref is None else ref
    med = np.median(ref)
    mad = np.median(np.abs(ref - med)) * 1.4826 + 1e-9
    return (x - med) / mad


def envelope(emg, gyro, eog, params: Params = Params()):
    env = robust_z(emg) + robust_z(gyro)
    if params.use_eog:
        env = env + robust_z(eog)
    return signal.sosfiltfilt(signal.butter(2, 3.0 / (FS / 2), output="sos"), env)


def find_repetitions(data: np.ndarray, params: Params = Params()) -> np.ndarray:
    env = envelope(*raw_activity(data, params), params=params)
    peaks, _ = signal.find_peaks(robust_z(env), height=params.peak_z, distance=int(params.min_gap_s * FS))
    return peaks


def find_other_movements(data: np.ndarray, peaks: np.ndarray, params: Params = Params()) -> np.ndarray:
    """Smaller activity bumps that are NOT the repetition itself: lowering the arm,
    turning the head back to centre, releasing a fist. Live onset detection fires
    on these too, so the classifier must learn to reject them."""
    env = robust_z(envelope(*raw_activity(data, params), params=params))
    bumps, _ = signal.find_peaks(env, height=params.peak_z * 0.5, distance=int(0.6 * FS))
    keep = [b for b in bumps if np.min(np.abs(peaks - b)) > int(0.8 * FS)] if len(peaks) else list(bumps)
    return np.asarray(keep, dtype=int)


def epoch_at(data, peak, params: Params = Params()):
    start = peak - int(params.epoch_pre_s * FS)
    stop = start + int(params.epoch_s * FS)
    return data[start:stop] if start >= 0 and stop <= len(data) else None


def arm_epoch_at(data, peak, params: Params = Params()):
    start = peak - int(params.arm_pre_s * FS)
    stop = peak + int(params.arm_post_s * FS)
    return data[start:stop] if start >= 0 and stop <= len(data) else None


# ------------------------------------------------------------------ features

def band_features(window: np.ndarray, params: Params = Params()) -> np.ndarray:
    eeg = clean_eeg(window[:, EEG], params)
    freqs, psd = signal.welch(eeg, fs=FS, nperseg=min(256, len(eeg)), axis=0)
    logp = np.vstack([np.log10(psd[(freqs >= lo) & (freqs < hi)].sum(axis=0) + 1e-12) for lo, hi in params.bands])
    return np.concatenate([logp.ravel(), logp[:, 1] - logp[:, 3], logp[:, 0] - logp[:, 6]])


def imu_features(window: np.ndarray) -> np.ndarray:
    acc, gyr = window[:, ACC], window[:, GYR]
    return np.concatenate([
        acc.mean(axis=0), acc.max(axis=0) - acc.min(axis=0),
        gyr.mean(axis=0), gyr.std(axis=0),
        np.percentile(gyr, 95, axis=0), np.percentile(gyr, 5, axis=0),
    ])


def emg_features(window: np.ndarray, params: Params = Params()) -> np.ndarray:
    eeg = clean_eeg(window[:, EEG], params)
    x = signal.sosfiltfilt(bandpass_sos(30, 100), eeg, axis=0)
    return np.log10((x ** 2).mean(axis=0) + 1e-12)


def covariances(window: np.ndarray, params: Params = Params()) -> list[np.ndarray]:
    eeg = clean_eeg(window[:, EEG], params)
    out = []
    for lo, hi in params.cov_bands:
        x = signal.sosfiltfilt(bandpass_sos(lo, hi), eeg, axis=0)
        c = np.cov(x.T)
        out.append(c + np.eye(len(c)) * np.trace(c) * 1e-3)
    return out


def tangent(cov: np.ndarray, ref_isqrt: np.ndarray) -> np.ndarray:
    """Project a covariance onto the tangent space at the training mean."""
    m = linalg.logm(ref_isqrt @ cov @ ref_isqrt).real
    iu = np.triu_indices(len(m))
    return m[iu] * np.where(iu[0] == iu[1], 1.0, np.sqrt(2.0))


def tangent_reference(windows, params: Params = Params()) -> list[np.ndarray]:
    covs = [covariances(w, params) for w in windows]
    refs = []
    for b in range(len(params.cov_bands)):
        mean = np.mean([c[b] for c in covs], axis=0)
        refs.append(linalg.inv(linalg.sqrtm(mean)).real)
    return refs


def full_features(window, refs, params: Params = Params()) -> np.ndarray:
    covs = covariances(window, params)
    return np.concatenate(
        [band_features(window, params), imu_features(window)] + [tangent(c, r) for c, r in zip(covs, refs)]
    )


def movement_shape(window, params: Params = Params()) -> np.ndarray:
    """Accelerometer (relative to the window start) and gyro, smoothed to 5 Hz and
    resampled to `wave_points` per axis: the trajectory of the movement."""
    acc = window[:, ACC] - window[:20, ACC].mean(axis=0)
    gyr = window[:, GYR]
    smooth = signal.butter(2, 5.0 / (FS / 2), output="sos")
    shape = lambda x: signal.resample(signal.sosfiltfilt(smooth, x, axis=0), params.wave_points, axis=0)
    return np.concatenate([shape(acc).ravel(), shape(gyr).ravel()])


def arm_side_features(arm_window, params: Params = Params()) -> np.ndarray:
    """Arm left/right: IMU summary + EMG + movement shape. Validated 92 % vs 83 % without the shape."""
    return np.concatenate([imu_features(arm_window), emg_features(arm_window, params),
                           movement_shape(arm_window, params)])


# ------------------------------------------------------------------ novelty

class Novelty:
    """Distance from the training gestures (Mahalanobis, shrunk covariance).

    A classifier always picks one of its classes, even for a twitch it never saw.
    This answers "does this window look like ANY trained gesture?" first.
    """

    def __init__(self, X):
        self.scaler = StandardScaler().fit(X)
        self.cov = LedoitWolf().fit(self.scaler.transform(X))

    def distance(self, X):
        return np.sqrt(self.cov.mahalanobis(self.scaler.transform(np.atleast_2d(X))))


# ------------------------------------------------------------------ unified features

def input_features(window, arm_window, refs, params: Params = Params()) -> np.ndarray:
    """One feature vector for any input, in two blocks (see feature_blocks):
    'full'     brain/muscle bands, IMU, channel covariance over the 1 s window
    'movement' IMU summary, EMG and movement shape over the longer window"""
    return np.concatenate([full_features(window, refs, params), arm_side_features(arm_window, params)])


def feature_blocks(window, arm_window, refs, params: Params = Params()) -> dict:
    """Column ranges of each block inside input_features()."""
    n_full = len(full_features(window, refs, params))
    n_all = n_full + len(arm_side_features(arm_window, params))
    return {"full": (0, n_full), "movement": (n_full, n_all), "all": (0, n_all)}


class Block:
    """A model that only looks at one block of columns of input_features()."""

    def __init__(self, model, cols):
        self.model, self.cols = model, cols
        self.classes_ = model.classes_

    def predict_proba(self, X):
        return self.model.predict_proba(np.atleast_2d(X)[:, self.cols[0]:self.cols[1]])
