"""Simple flight with three inputs, driven through Tello/Mover.py (the team's keyboard controller):

    jaw (1st time)  -> key Q  -> takeoff
    cuello          -> key W  -> forward 1 s   (turn the head to the RIGHT, then back)
    blink           -> key S  -> back 1 s
    jaw (2nd time)  -> key E  -> land

Each gesture becomes the key Mover.py would get; Mover.get_keyboard_input() turns it into the command, and it is
executed the way Mover.main() does it (tello.takeoff / tello.land / tello.send_rc_control). The gestures come from
the same detectors, arbiter and calibration as fly.py (data/calibration/thresholds.json when it exists).

    python scripts/artifacts/vuelo.py               # REAL Tello: connect to its Wi-Fi first
    python scripts/artifacts/vuelo.py --dry-run     # no drone, prints what it would send
    python scripts/artifacts/vuelo.py --replay <csv> --dry-run   # a recording, no hardware

Ctrl+C lands and exits at any time.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import _paths  # noqa: F401
from _live import CsvReplayClient
from eeg.arbiter import InputArbiter
from eeg.calibration import DEFAULT_PATH as CALIBRATION, calibrated_params, load as load_calibration
from eeg.preprocess import ARTIFACT_CLEANING, GAUGE_CLEANING, SAMPLE_RATE, artifact_feature
from lsl.client import DEFAULT_STREAM_NAME, LslClient

sys.path.insert(0, str(_paths.ROOT / "Tello"))
from Mover import get_keyboard_input  # noqa: E402

INPUTS = ("jaw", "cuello", "blink")
KEYS = {"cuello": "w", "blink": "s"}  # jaw is q or e depending on whether it is flying
PULSE_S = 1.0  # how long a forward/back command is held
RC_REFRESH_S = 0.1  # resend the current RC command this often, like Mover.py's loop (keeps the Tello awake)
MIN_BATTERY = 20
STATUS_INTERVAL_S = 0.5
LOOP_SLEEP_S = 0.005
HOVER = (0, 0, 0, 0)


class DryRunTello:
    """Prints what would be sent to the drone, with the same methods Mover.py uses."""

    def connect(self) -> None:
        print("[dry-run] connect")

    def get_battery(self) -> int:
        return 100

    def takeoff(self) -> None:
        print("[dry-run] tello.takeoff()")

    def land(self) -> None:
        print("[dry-run] tello.land()")

    def send_rc_control(self, lr: int, fb: int, ud: int, yv: int) -> None:
        pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Jaw: takeoff/land. Neck: forward. Blink: back. Through Tello/Mover.py")
    parser.add_argument("--dry-run", action="store_true", help="Do not connect to the Tello; print instead")
    parser.add_argument("--stream", default=DEFAULT_STREAM_NAME, help="Unicorn raw LSL stream name")
    parser.add_argument("--replay", type=Path, help="Run on a recorded CSV instead of LSL (use with --dry-run)")
    parser.add_argument("--threshold", action="append", default=[], metavar="INPUT=VALUE", help="Override a threshold")
    parser.add_argument("--why", action="store_true", help="Also print the firings the arbiter dropped, and why")
    return parser.parse_args()


def build_arbiter(args: argparse.Namespace) -> InputArbiter:
    if load_calibration():
        arbiter = InputArbiter(INPUTS, params=calibrated_params())
    else:
        arbiter = InputArbiter(INPUTS)
    for item in args.threshold:
        name, _, value = item.partition("=")
        arbiter.with_threshold(name, float(value))
    return arbiter


def connect_tello(dry_run: bool):
    if dry_run:
        tello = DryRunTello()
    else:
        from djitellopy import Tello

        tello = Tello()
    print("Conectando con el dron Tello...")
    tello.connect()
    battery = tello.get_battery()
    print(f"Nivel de batería: {battery}%")
    if battery < MIN_BATTERY:
        print("Batería demasiado baja para un vuelo seguro. Carga el dron e intenta de nuevo.")
        return None
    return tello


class Flight:
    """Executes Mover.py commands and holds forward/back for PULSE_S, then hovers."""

    def __init__(self, tello) -> None:
        self.tello = tello
        self.is_flying = False
        self._rc = HOVER
        self._rc_until = 0.0
        self._next_send = 0.0

    def gesture(self, name: str, now: float) -> str:
        key = ("e" if self.is_flying else "q") if name == "jaw" else KEYS[name]
        command, rc = get_keyboard_input(ord(key))
        if command == "TAKEOFF" and not self.is_flying:
            print("--> Despegando...")
            self.tello.takeoff()
            self.is_flying = True
            return f"key {key.upper()}: TAKEOFF"
        if command == "LAND" and self.is_flying:
            self.stop()
            print("--> Aterrizando...")
            self.tello.land()
            self.is_flying = False
            return f"key {key.upper()}: LAND"
        if command == "FLIGHT" and self.is_flying:
            self._rc, self._rc_until, self._next_send = rc, now + PULSE_S, 0.0
            return f"key {key.upper()}: rc{rc} for {PULSE_S:.0f} s"
        return f"key {key.upper()}: ignored (take off first with the jaw)"

    def tick(self, now: float) -> None:
        """Keep sending the current RC command (or hover) while flying, like Mover.py's loop."""
        if not self.is_flying or now < self._next_send:
            return
        if now >= self._rc_until:
            self._rc = HOVER
        self.tello.send_rc_control(*self._rc)
        self._next_send = now + RC_REFRESH_S

    def stop(self) -> None:
        self._rc, self._rc_until = HOVER, 0.0
        if self.is_flying:
            self.tello.send_rc_control(*HOVER)

    def shutdown(self) -> None:
        print("\nCerrando programa y asegurando el dron...")
        try:
            self.tello.send_rc_control(*HOVER)
            if self.is_flying:
                self.tello.land()
        except Exception:
            pass
        self.is_flying = False
        print("Programa finalizado de forma segura.")


def drain(client) -> None:
    """Drop the samples that queued while takeoff/land blocked, so old gestures are not replayed."""
    if isinstance(client, CsvReplayClient):
        return
    while client.pull_chunk(timeout=0.0, max_samples=1024).size:
        pass


def main() -> None:
    args = parse_args()
    replay = args.replay is not None
    dry_run = args.dry_run or replay
    print(f"Mode: {'DRY-RUN (no drone)' if dry_run else 'LIVE - real Tello'}")
    arbiter = build_arbiter(args)
    print("Thresholds: " + (f"calibrated ({CALIBRATION})" if load_calibration() else "tested defaults"))

    # 1. Connect to the drone and check the battery (as Tello/Inicio.py does)
    tello = connect_tello(dry_run)
    if tello is None:
        return
    flight = Flight(tello)

    # 2. Subscribe to the headset (or the recording)
    client = CsvReplayClient(args.replay) if replay else LslClient()
    if not client.connect(stream_name=args.stream):
        raise SystemExit(1)

    clock = client.now if replay else time.monotonic
    print("\n  JAW clench   -> Q takeoff (1st) / E land (2nd)")
    print("  Head RIGHT  -> W forward")
    print("  BLINK       -> S back")
    print("  Ctrl+C      -> land and exit\n")

    # 3. One gesture at a time from the arbiter, sent as Mover.py would
    next_status = 0.0
    try:
        while True:
            chunk = client.pull_chunk(timeout=0.05)
            if chunk.size == 0:
                if replay and client.finished:
                    break
                flight.tick(clock())
                continue
            window = client.window()
            if len(window) < SAMPLE_RATE:
                continue

            values = {name: artifact_feature(window, ARTIFACT_CLEANING[name]) for name in INPUTS}
            gauges = {name: artifact_feature(window, spec) for name, spec in GAUGE_CLEANING.items()}
            now = clock()
            confirmed = arbiter.update(values, now, gauges)
            stamp = f"t={now:5.1f}s  " if replay else ""

            if args.why:
                for name, reason in arbiter.dropped:
                    print(f"    dropped {name}: {reason}")
            if confirmed:
                print(f">>> {confirmed:7s} {stamp}-> {flight.gesture(confirmed, now)}")
                if confirmed == "jaw":  # takeoff/land block for seconds; start fresh after them
                    drain(client)
                    arbiter = build_arbiter(args)
            elif now >= next_status:
                state = "FLYING" if flight.is_flying else "grounded"
                print("  ".join(f"{name}={values[name]:6.1f}" for name in INPUTS) + f"   {state}")
                next_status = now + STATUS_INTERVAL_S

            flight.tick(now)
            if not replay:
                time.sleep(LOOP_SLEEP_S)
    except KeyboardInterrupt:
        print("\n[!] Salida de emergencia activada.")
    except Exception as exc:
        print(f"\nError durante la ejecución: {exc}")
    finally:
        # 4. Always land and release resources
        client.close()
        flight.shutdown()


if __name__ == "__main__":
    main()
