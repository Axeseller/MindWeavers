"""Check that this computer can run the artifact scripts: Python, libraries, the Unicorn LSL stream, the Tello.

    python scripts/artifacts/doctor.py            # Python, libraries and LSL stream
    python scripts/artifacts/doctor.py --tello    # also ping the Tello (must be on its Wi-Fi)
"""

from __future__ import annotations

import argparse
import importlib
import sys

import _paths  # noqa: F401

LIBRARIES = ("numpy", "scipy", "pylsl", "cv2", "djitellopy")
STREAM_NAME = "UnicornRecorderRawDataLSLStream"
EXPECTED_RATE = 250
MIN_CHANNELS = 14


def check(label: str, ok: bool, detail: str = "") -> bool:
    print(f"  [{'OK' if ok else 'FAIL'}] {label}" + (f": {detail}" if detail else ""))
    return ok


def check_python() -> bool:
    version = sys.version_info
    return check("Python 3.9+", version >= (3, 9), f"{version.major}.{version.minor} at {sys.executable}")


def check_libraries() -> bool:
    ok = True
    for name in LIBRARIES:
        try:
            importlib.import_module(name)
            check(name, True)
        except ImportError as exc:
            ok = check(name, False, f"{exc}. Run: pip install -r requirements.txt")
    return ok


def check_stream() -> bool:
    try:
        from pylsl import resolve_byprop
    except ImportError:
        return check("LSL stream", False, "pylsl missing")
    streams = resolve_byprop("name", STREAM_NAME, timeout=5.0)
    if not streams:
        return check("LSL stream", False, f"'{STREAM_NAME}' not found. Open Unicorn Recorder and turn on LSL.")
    info = streams[0]
    channels, rate = int(info.channel_count()), float(info.nominal_srate())
    ok = channels >= MIN_CHANNELS and abs(rate - EXPECTED_RATE) < 1
    return check("LSL stream", ok, f"{channels} channels at {rate:.0f} Hz (need >= {MIN_CHANNELS} at {EXPECTED_RATE})")


def check_tello() -> bool:
    try:
        from djitellopy import Tello
    except ImportError:
        return check("Tello", False, "djitellopy missing")
    try:
        tello = Tello()
        tello.connect()
        return check("Tello", True, f"battery {tello.get_battery()}%")
    except Exception as exc:
        return check("Tello", False, f"{exc}. Connect to the TELLO-xxxx Wi-Fi first.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Check the setup for the artifact scripts")
    parser.add_argument("--tello", action="store_true", help="Also connect to the Tello")
    args = parser.parse_args()
    print("Checking...")
    results = [check_python(), check_libraries(), check_stream()]
    if args.tello:
        results.append(check_tello())
    print("\nAll good. Run: python src/app.py --dry-run" if all(results) else "\nFix the FAIL lines above and run again.")
    raise SystemExit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
