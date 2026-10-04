from __future__ import annotations

from collections import deque

import numpy as np

DEFAULT_STREAM_NAME = "UnicornRecorderRawDataLSLStream"
SAMPLE_RATE = 250
EEG_CHANNEL_COUNT = 8
TOTAL_CHANNEL_COUNT = 18
BUFFER_SECONDS = 1.0


class LslClient:
    """Subscribe to Unicorn raw LSL and keep a one-second ring buffer."""

    def __init__(self, buffer_seconds: float = BUFFER_SECONDS) -> None:
        self._inlet = None
        self._channel_count = 0
        max_samples = int(SAMPLE_RATE * buffer_seconds)
        self._buffer: deque[np.ndarray] = deque(maxlen=max_samples)

    @property
    def channel_count(self) -> int:
        return self._channel_count

    def connect(self, stream_name: str = DEFAULT_STREAM_NAME, timeout: float = 8.0) -> bool:
        try:
            from pylsl import StreamInlet, resolve_byprop
        except ImportError as exc:
            raise RuntimeError("pylsl is not installed. Run: pip install pylsl") from exc

        print(f"Looking for LSL stream '{stream_name}'...")
        streams = resolve_byprop("name", stream_name, timeout=timeout)
        if not streams:
            print(f"No LSL stream named '{stream_name}'. Is Unicorn Recorder raw LSL on?")
            return False
        self._inlet = StreamInlet(streams[0], max_buflen=2)
        self._channel_count = int(streams[0].channel_count())
        print(f"Connected to '{streams[0].name()}' ({self._channel_count} channels)")
        return True

    def pull_chunk(self, timeout: float = 0.0, max_samples: int = 64) -> np.ndarray:
        if self._inlet is None:
            return np.empty((0, self._channel_count))
        samples, _timestamps = self._inlet.pull_chunk(timeout=timeout, max_samples=max_samples)
        if not samples:
            return np.empty((0, self._channel_count))
        chunk = np.asarray(samples, dtype=np.float64)
        for row in chunk:
            self._buffer.append(row)
        return chunk

    def window(self) -> np.ndarray:
        if not self._buffer:
            return np.empty((0, self._channel_count))
        return np.vstack(self._buffer)

    def close(self) -> None:
        self._inlet = None
        self._buffer.clear()
