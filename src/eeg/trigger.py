from __future__ import annotations

import time

from eeg.detectors import ArtifactDetector, DetectorConfig
from eeg.preprocess import SAMPLE_RATE, extract_features, preprocess_window
from lsl.client import DEFAULT_STREAM_NAME, LslClient


class EegTrigger:
    """Non-blocking live EEG -> detector events, for loops that also drive video and keyboard.

    Same signal path as the original jaw takeoff script: wait for a full 1 s window, then filter, extract features
    and update the detector only when new samples arrive.
    """

    def __init__(self, config: DetectorConfig, client: LslClient | None = None) -> None:
        self.detector = ArtifactDetector(config)
        self.client = client or LslClient()
        self.jaw_rms = 0.0
        self.blink_amp = 0.0

    def connect(self, stream_name: str = DEFAULT_STREAM_NAME) -> bool:
        return self.client.connect(stream_name=stream_name)

    def poll(self, now: float | None = None) -> list[str]:
        chunk = self.client.pull_chunk(timeout=0.0)
        if chunk.size == 0:
            return []
        window = self.client.window()
        if len(window) < SAMPLE_RATE:
            return []
        self.jaw_rms, self.blink_amp = extract_features(preprocess_window(window))
        return self.detector.update(self.jaw_rms, self.blink_amp, time.monotonic() if now is None else now)

    def close(self) -> None:
        self.client.close()
