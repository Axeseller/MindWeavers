from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import signal

SAMPLE_RATE = 250
EEG_CHANNEL_COUNT = 8
MIN_FILTER_SAMPLES = 32
NOTCH_FREQ = 60.0
BANDPASS = (1.0, 40.0)
JAW_BAND = (15.0, 40.0)
BLINK_BAND = (1.0, 10.0)
BLINK_CHANNELS = (0, 1)
EYES_CLOSED_BAND = (8.0, 13.0)
EYES_CLOSED_CHANNELS = (5, 6, 7)


def preprocess_window(window: np.ndarray, fs: int = SAMPLE_RATE) -> np.ndarray:
    """Notch + 1–40 Hz bandpass on EEG columns. Leaves IMU columns unchanged."""
    if window.size == 0 or window.shape[0] < MIN_FILTER_SAMPLES:
        return window
    eeg = window[:, :EEG_CHANNEL_COUNT]
    filtered = _notch(eeg, NOTCH_FREQ, fs)
    filtered = _bandpass(filtered, BANDPASS[0], BANDPASS[1], fs)
    out = window.copy()
    out[:, :EEG_CHANNEL_COUNT] = filtered
    return out


def extract_features(window: np.ndarray, fs: int = SAMPLE_RATE) -> tuple[float, float]:
    """Return (jaw_rms, blink_amp) from the latest EEG window."""
    if window.size == 0:
        return 0.0, 0.0
    eeg = window[:, :EEG_CHANNEL_COUNT]
    jaw_band = _bandpass(eeg, JAW_BAND[0], JAW_BAND[1], fs)
    blink_band = _bandpass(eeg, BLINK_BAND[0], BLINK_BAND[1], fs)
    jaw_rms = float(np.sqrt(np.mean(np.square(jaw_band))))
    blink_cols = blink_band[:, list(BLINK_CHANNELS)]
    blink_amp = float(np.mean(np.abs(blink_cols)))
    return jaw_rms, blink_amp


def extract_eye_features(window: np.ndarray, fs: int = SAMPLE_RATE) -> tuple[float, float]:
    """Return (blink_peak, eyes_closed_amp) from the latest EEG window."""
    if window.size == 0:
        return 0.0, 0.0
    eeg = window[:, :EEG_CHANNEL_COUNT]
    blink_band = _bandpass(eeg, BLINK_BAND[0], BLINK_BAND[1], fs)
    blink_cols = blink_band[:, list(BLINK_CHANNELS)]
    blink_peak = float(np.max(np.abs(blink_cols))) if blink_cols.size else 0.0
    closed_band = _bandpass(eeg, EYES_CLOSED_BAND[0], EYES_CLOSED_BAND[1], fs)
    closed_cols = closed_band[:, list(EYES_CLOSED_CHANNELS)]
    if closed_cols.size == 0:
        return blink_peak, 0.0
    eyes_closed_amp = float(np.sqrt(np.mean(np.square(closed_cols))))
    return blink_peak, eyes_closed_amp


def _bandpass(data: np.ndarray, low: float, high: float, fs: int, order: int = 4) -> np.ndarray:
    if data.shape[0] < MIN_FILTER_SAMPLES:
        return data
    nyq = fs / 2.0
    sos = signal.butter(order, [low / nyq, high / nyq], btype="bandpass", output="sos")
    return signal.sosfiltfilt(sos, data, axis=0)


def _notch(data: np.ndarray, freq: float, fs: int, q: float = 30.0) -> np.ndarray:
    if data.shape[0] < MIN_FILTER_SAMPLES:
        return data
    b, a = signal.iirnotch(freq, q, fs)
    return signal.filtfilt(b, a, data, axis=0)


# ---------------------------------------------------------------------------
# Per-artifact cleaning. One entry per recorded artifact; scripts/artifacts/<name>.py reads its own.
# Unicorn columns: 0-7 EEG (Fz, C3, Cz, C4, Pz, PO7, Oz, PO8), 8-10 accelerometer, 11-13 gyroscope (x, y, z).
# ---------------------------------------------------------------------------
GYRO_COLUMNS = (11, 12, 13)
ALL_EEG = tuple(range(EEG_CHANNEL_COUNT))
FZ, C3, CZ, C4, PZ, PO7, OZ, PO8 = ALL_EEG
GYRO_X, GYRO_Y, GYRO_Z = 0, 1, 2


@dataclass(frozen=True)
class ArtifactCleaning:
    """How one artifact's feature is cleaned and measured from the latest 1 s window.

    source:   "eeg" uses EEG channels; "gyro" uses gyroscope axes (channels are 0=x, 1=y, 2=z).
    band:     bandpass in Hz (EEG only). None skips it.
    car:      common average reference, removes what all 8 electrodes share (EEG only).
    recent_s: measure only the newest part of the window, so onsets are seen early.
    stat:     rms | peak (largest positive) | mean (signed) | p2p (max - min).
    """

    source: str = "eeg"
    channels: tuple[int, ...] = ALL_EEG
    band: tuple[float, float] | None = None
    filter_order: int = 4
    car: bool = False
    notch: bool = True
    recent_s: float = 1.0
    stat: str = "rms"


ARTIFACT_CLEANING: dict[str, ArtifactCleaning] = {
    # Same signal path as extract_features() so jaw_takeoff calibration still holds.
    "jaw": ArtifactCleaning(band=JAW_BAND),
    # A blink is a one-way frontal deflection. Signed and 2nd-order so the filter does not ring into a second hump.
    "blink": ArtifactCleaning(channels=(FZ,), band=(0.5, 8.0), filter_order=2, car=True, recent_s=0.5, stat="peak"),
    # Closed eyes raise occipital alpha.
    "cerrar_ojos": ArtifactCleaning(channels=(PO7, OZ, PO8), band=EYES_CLOSED_BAND, car=True, recent_s=0.5),
    # Real head turns: yaw rate, signed (left positive).
    "cuello_izq": ArtifactCleaning(source="gyro", channels=(GYRO_Z,), recent_s=0.2, stat="mean"),
    "cuello_der": ArtifactCleaning(source="gyro", channels=(GYRO_Z,), recent_s=0.2, stat="mean"),
    # Imagined turns: no EEG feature separated them from rest; the residual head tilt does (left negative).
    "giro_imag_izq": ArtifactCleaning(source="gyro", channels=(GYRO_Y,), recent_s=0.2, stat="mean"),
    "giro_imag_der": ArtifactCleaning(source="gyro", channels=(GYRO_Y,), recent_s=0.2, stat="mean"),
    # Facial EMG. Frowning is strong and broad (15-40 Hz, no CAR so the shared muscle signal is kept);
    # smiling is weaker and only shows in high gamma once the shared part is removed.
    "enojado": ArtifactCleaning(band=JAW_BAND, recent_s=0.5),
    "happy": ArtifactCleaning(band=(30.0, 100.0), car=True, recent_s=0.5),
    # Raising the left arm sways the head: yaw goes negative.
    "brazo_izq": ArtifactCleaning(source="gyro", channels=(GYRO_Z,), recent_s=0.2, stat="mean"),
    # Fists: the scalp sees almost no hand EMG, only a small body movement. No axis tells left from right.
    "puno_izq": ArtifactCleaning(source="gyro", channels=(GYRO_X, GYRO_Y, GYRO_Z), recent_s=0.3),
    "puno_der": ArtifactCleaning(source="gyro", channels=(GYRO_X, GYRO_Y, GYRO_Z), recent_s=0.3),
}


def artifact_feature(window: np.ndarray, cleaning: ArtifactCleaning, fs: int = SAMPLE_RATE) -> float:
    """Clean the latest window the way `cleaning` says and reduce it to one number."""
    if window.size == 0 or window.shape[0] < MIN_FILTER_SAMPLES:
        return 0.0
    if cleaning.source == "gyro":
        gyro = window[:, list(GYRO_COLUMNS)]
        data = (gyro - np.median(gyro, axis=0))[:, list(cleaning.channels)]
    else:
        eeg = window[:, :EEG_CHANNEL_COUNT] - window[:, :EEG_CHANNEL_COUNT].mean(axis=0)
        if cleaning.car:
            eeg = eeg - eeg.mean(axis=1, keepdims=True)
        if cleaning.notch:
            eeg = _notch(eeg, NOTCH_FREQ, fs)
        if cleaning.band is not None:
            eeg = _bandpass(eeg, cleaning.band[0], cleaning.band[1], fs, cleaning.filter_order)
        data = eeg[:, list(cleaning.channels)]
    recent = data[-max(1, int(cleaning.recent_s * fs)) :]
    return _reduce(recent, cleaning.stat)


def _reduce(data: np.ndarray, stat: str) -> float:
    if stat == "rms":
        return float(np.sqrt(np.mean(np.square(data))))
    if stat == "peak":
        return float(np.max(data))
    if stat == "mean":
        return float(np.mean(data))
    if stat == "p2p":
        return float(np.ptp(data))
    raise ValueError(f"Unknown stat '{stat}'")
