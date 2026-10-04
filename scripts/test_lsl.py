from __future__ import annotations

import argparse
import time

import _paths  # noqa: F401
from lsl.client import DEFAULT_STREAM_NAME, LslClient


def main() -> None:
    parser = argparse.ArgumentParser(description="Print live Unicorn raw LSL samples")
    parser.add_argument("--stream", default=DEFAULT_STREAM_NAME)
    parser.add_argument("--seconds", type=float, default=10.0)
    args = parser.parse_args()

    client = LslClient()
    if not client.connect(stream_name=args.stream):
        raise SystemExit(1)

    end = time.monotonic() + args.seconds
    printed = 0
    try:
        while time.monotonic() < end:
            chunk = client.pull_chunk(timeout=0.2)
            if chunk.size == 0:
                continue
            row = chunk[-1]
            printed += len(chunk)
            eeg = " ".join(f"{value:7.1f}" for value in row[:8])
            print(f"n={printed:5d}  EEG[{eeg}]")
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        client.close()
    print(f"Received {printed} samples from '{args.stream}'.")


if __name__ == "__main__":
    main()
