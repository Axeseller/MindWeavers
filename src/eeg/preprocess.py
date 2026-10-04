from __future__ import annotations

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


def _bandpass(data: np.ndarray, low: float, high: float, fs: int) -> np.ndarray:
    if data.shape[0] < MIN_FILTER_SAMPLES:
        return data
    nyq = fs / 2.0
    sos = signal.butter(4, [low / nyq, high / nyq], btype="bandpass", output="sos")
    return signal.sosfiltfilt(sos, data, axis=0)


def _notch(data: np.ndarray, freq: float, fs: int, q: float = 30.0) -> np.ndarray:
    if data.shape[0] < MIN_FILTER_SAMPLES:
        return data
    b, a = signal.iirnotch(freq, q, fs)
    return signal.filtfilt(b, a, data, axis=0)
