from __future__ import annotations

import argparse
import csv
import time
from datetime import datetime
from pathlib import Path

import _paths  # noqa: F401
from lsl.client import DEFAULT_STREAM_NAME, TOTAL_CHANNEL_COUNT, LslClient

OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "baselines"


def main() -> None:
    parser = argparse.ArgumentParser(description="Record labeled Unicorn raw LSL to CSV")
    parser.add_argument("--label", required=True, help="Artifact label, e.g. jaw or blink")
    parser.add_argument("--seconds", type=float, default=30.0)
    parser.add_argument("--stream", default=DEFAULT_STREAM_NAME)
    args = parser.parse_args()

    client = LslClient()
    if not client.connect(stream_name=args.stream):
        raise SystemExit(1)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = OUT_DIR / f"{args.label}_{stamp}.csv"
    channel_count = client.channel_count or TOTAL_CHANNEL_COUNT
    header = ["timestamp"] + [f"ch{i}" for i in range(channel_count)] + ["label"]

    print(f"Recording '{args.label}' for {args.seconds}s → {path}")
    print("Perform the artifact clearly, then rest.")
    rows = 0
    end = time.monotonic() + args.seconds
    try:
        with path.open("w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(header)
            rows += _record_loop(client, writer, args.label, end, channel_count)
    except KeyboardInterrupt:
        print("\nStopped early.")
    finally:
        client.close()
    print(f"Wrote {rows} samples to {path}")


def _record_loop(client: LslClient, writer, label: str, end: float, channel_count: int) -> int:
    rows = 0
    while time.monotonic() < end:
        chunk = client.pull_chunk(timeout=0.2)
        now = time.time()
        for sample in chunk:
            padded = list(sample[:channel_count])
            if len(padded) < channel_count:
                padded.extend([0.0] * (channel_count - len(padded)))
            writer.writerow([now, *padded, label])
            rows += 1
    return rows


if __name__ == "__main__":
    main()
