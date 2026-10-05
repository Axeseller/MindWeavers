"""Simple flight with three inputs, driven through Tello/Mover.py (the team's keyboard controller):

    jaw (1st time)  -> key Q  -> takeoff
    cuello          -> key W  -> forward 1 s   (turn the head to either side, then back)
    blink           -> key S  -> back 1 s
    jaw (2nd time)  -> key E  -> land

Each gesture becomes the key Mover.py would get; Mover.get_keyboard_input() turns it into the command, and it is
executed the way Mover.main() does it (tello.takeoff / tello.land / tello.send_rc_control). The gestures come from
the shared detectors, arbiter and calibration (data/calibration/thresholds.json when it exists).

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
from eeg.arbiter import FACE_LIMITS, GATES, InputArbiter
from eeg.calibration import DEFAULT_PATH as CALIBRATION, apply_saved_gates, calibrated_params, load as load_calibration
from eeg.preprocess import ARTIFACT_CLEANING, GAUGE_CLEANING, SAMPLE_RATE, artifact_feature
from lsl.client import DEFAULT_STREAM_NAME, LslClient

sys.path.insert(0, str(_paths.ROOT / "Tello"))
from Mover import get_keyboard_input  # noqa: E402

INPUTS = ("jaw", "cuello", "blink")
KEYS = {"cuello": "w", "blink": "s"}  # jaw is q or e depending on whether it is flying
CONTROLS = (
    "  JAW clench   -> Q takeoff (1st) / E land (2nd)",
    "  Turn head   -> W forward (either side)",
    "  BLINK       -> S back",
)
PULSE_S = 1.0  # how long a forward/back command is held
RC_REFRESH_S = 0.1  # resend the current RC command this often, like Mover.py's loop (keeps the Tello awake)
MIN_BATTERY = 20
HOT_TEMPERATURE = 85  # °C; around 90 the Tello refuses to take off and shuts down to cool
NO_DATA_WARN_S = 3.0  # say so when the headset sends nothing for this long
STATUS_INTERVAL_S = 0.5
LOOP_SLEEP_S = 0.005
HOVER = (0, 0, 0, 0)


class DryRunTello:
    """Prints what would be sent to the drone, with the same methods Mover.py uses."""

    def connect(self) -> None:
        print("[dry-run] connect")

    def get_battery(self) -> int:
        return 100

    def get_highest_temperature(self) -> int:
        return 60

    def takeoff(self) -> None:
        print("[dry-run] tello.takeoff()")

    def land(self) -> None:
        print("[dry-run] tello.land()")

    def rotate_clockwise(self, degrees: int) -> None:
        print(f"[dry-run] tello.rotate_clockwise({degrees})")

    def send_rc_control(self, lr: int, fb: int, ud: int, yv: int) -> None:
        pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Jaw: takeoff/land. Neck: forward. Blink: back. Through Tello/Mover.py")
    parser.add_argument("--dry-run", action="store_true", help="Do not connect to the Tello; print instead")
    parser.add_argument("--stream", default=DEFAULT_STREAM_NAME, help="Unicorn raw LSL stream name")
    parser.add_argument("--replay", type=Path, help="Run on a recorded CSV instead of LSL (use with --dry-run)")
    parser.add_argument("--threshold", action="append", default=[], metavar="INPUT=VALUE", help="Override a threshold")
    parser.add_argument("--why", action="store_true", help="Also print the firings the arbiter dropped, and why")
    parser.add_argument("--no-calibration", action="store_true", help="Ignore data/calibration/thresholds.json")
    parser.add_argument(
        "--loose-faces",
        action="store_true",
        help="Drop the shape checks on angry/happy (EMG pattern, eyes, blink): only their thresholds decide",
    )
    return parser.parse_args()


def build_arbiter(args: argparse.Namespace, inputs: tuple[str, ...] = INPUTS) -> InputArbiter:
    gates = {k: v for k, v in GATES.items() if k not in ("angry", "happy")} if args.loose_faces else GATES
    if not args.no_calibration:
        apply_saved_gates()
    if load_calibration() and not args.no_calibration:
        arbiter = InputArbiter(inputs, params=calibrated_params(), gates=gates)
    else:
        arbiter = InputArbiter(inputs, gates=gates)
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
    temperature = tello.get_highest_temperature()
    print(f"Temperatura: {temperature}°C")
    if temperature >= HOT_TEMPERATURE:
        print("[!] El Tello está caliente: puede negarse a despegar. Apágalo unos minutos o dale aire.")
    return tello


def takeoff_diagnosis(tello, error: Exception) -> str:
    """Why the Tello refused to take off, as far as it can tell us."""
    lines = [f"El Tello rechazó el despegue: {error}"]
    text = str(error).lower()
    try:
        battery = tello.get_battery()
        temperature = tello.get_highest_temperature()
        lines.append(f"  batería {battery}%, temperatura {temperature}°C")
        if battery < 30:
            lines.append("  -> batería baja: con menos de ~30% el Tello a veces se niega. Cámbiala.")
        if temperature >= HOT_TEMPERATURE:
            lines.append("  -> sobrecalentado: apágalo unos minutos.")
    except Exception:
        lines.append("  (no respondió a batería/temperatura: revisa el Wi-Fi del Tello)")
    if "imu" in text:
        lines.append("  -> calibra la IMU desde la app Tello (Configuración > Más > Calibrar IMU).")
    if "motor" in text:
        lines.append("  -> revisa que las hélices giren libres y sin protectores trabados.")
    lines.append("  Pon el dron en piso plano y con luz. Aprieta la mandíbula otra vez para reintentar.")
    return "\n".join(lines)


class Flight:
    """Executes Mover.py commands and holds forward/back for PULSE_S, then hovers.

    `turns` maps an input to an exact clockwise turn in degrees (tello.rotate_clockwise): Mover.py's R/T keys only
    spin while held, so they cannot give a precise angle.
    """

    def __init__(self, tello, keys: dict[str, str] = KEYS, turns: dict[str, int] | None = None) -> None:
        self.tello = tello
        self.keys = keys
        self.turns = turns or {}
        self.is_flying = False
        self._rc = HOVER
        self._rc_until = 0.0
        self._next_send = 0.0

    def gesture(self, name: str, now: float) -> str:
        if name in self.turns:
            return self.turn(self.turns[name])
        key = ("e" if self.is_flying else "q") if name == "jaw" else self.keys[name]
        command, rc = get_keyboard_input(ord(key))
        if command == "TAKEOFF" and not self.is_flying:
            print("--> Despegando...")
            try:
                self.tello.takeoff()
            except Exception as error:  # the drone answered "error": keep running so the pilot can retry
                print(takeoff_diagnosis(self.tello, error))
                return f"key {key.upper()}: TAKEOFF FAILED"
            self.is_flying = True
            return f"key {key.upper()}: TAKEOFF"
        if command == "LAND" and self.is_flying:
            self.stop()
            print("--> Aterrizando...")
            try:
                self.tello.land()
            except Exception as error:  # still flying: hover and let the pilot clench again (or Ctrl+C)
                print(f"El Tello no confirmó el aterrizaje: {error}. Sigue en el aire; aprieta otra vez o Ctrl+C.")
                return f"key {key.upper()}: LAND FAILED"
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


    def turn(self, degrees: int) -> str:
        """Exact turn to the right; blocks until the Tello finishes it."""
        if not self.is_flying:
            return f"turn {degrees}° ignored (take off first with the jaw)"
        self.stop()
        print(f"--> Girando {degrees}° a la derecha...")
        try:
            self.tello.rotate_clockwise(degrees)
        except Exception as error:  # the drone refused or timed out: keep flying, hover
            print(f"El Tello no confirmó el giro: {error}")
            return f"TURN {degrees}° FAILED"
        return f"TURN {degrees}° RIGHT"


def drain(client) -> None:
    """Drop the samples that queued while takeoff/land blocked, so old gestures are not replayed."""
    if isinstance(client, CsvReplayClient):
        return
    while client.pull_chunk(timeout=0.0, max_samples=1024).size:
        pass


def main(
    inputs: tuple[str, ...] = INPUTS,
    keys: dict[str, str] = KEYS,
    controls: tuple[str, ...] = CONTROLS,
    turns: dict[str, int] | None = None,
) -> None:
    """Run the flight with these inputs; `keys` maps each non-jaw input to its Mover.py key, `turns` to an exact
    clockwise turn."""
    args = parse_args()
    replay = args.replay is not None
    dry_run = args.dry_run or replay
    print(f"Mode: {'DRY-RUN (no drone)' if dry_run else 'LIVE - real Tello'}")
    arbiter = build_arbiter(args, inputs)
    source = f"calibrated ({CALIBRATION})" if load_calibration() and not args.no_calibration else "tested defaults"
    print(f"Thresholds: {source}")
    print("  " + "  ".join(f"{name}={arbiter.detectors[name].params.threshold:g}" for name in inputs))
    if {"angry", "happy"} & set(inputs):
        if args.loose_faces:
            print("  face checks: OFF (--loose-faces)")
        else:
            side = "<=" if FACE_LIMITS["frown_is_low"] else ">="
            print(f"  face checks: frown when frontal/occipital {side} {FACE_LIMITS['face_ratio']:.2f}, "
                  f"smile eye deflection <= {FACE_LIMITS['smile_max_blink']:.0f}")

    # 1. Connect to the drone and check the battery (as Tello/Inicio.py does)
    tello = connect_tello(dry_run)
    if tello is None:
        return
    flight = Flight(tello, keys, turns)

    # 2. Subscribe to the headset (or the recording)
    client = CsvReplayClient(args.replay) if replay else LslClient()
    if not client.connect(stream_name=args.stream):
        raise SystemExit(1)

    clock = client.now if replay else time.monotonic
    print()
    for line in controls:
        print(line)
    print("  Ctrl+C      -> land and exit\n")

    # 3. One gesture at a time from the arbiter, sent as Mover.py would
    next_status = 0.0
    last_data = time.monotonic()
    next_warning = last_data + NO_DATA_WARN_S
    print("Waiting for headset data...")
    try:
        while True:
            chunk = client.pull_chunk(timeout=0.05)
            if chunk.size == 0:
                if replay and client.finished:
                    break
                if not replay and time.monotonic() >= next_warning:
                    print(f"[!] No data from the headset for {time.monotonic() - last_data:.0f} s: is Unicorn "
                          "Recorder streaming (LSL on, headset connected)?")
                    next_warning = time.monotonic() + NO_DATA_WARN_S
                flight.tick(clock())
                continue
            last_data = time.monotonic()
            next_warning = last_data + NO_DATA_WARN_S
            window = client.window()
            if len(window) < SAMPLE_RATE:
                continue

            values = {name: artifact_feature(window, ARTIFACT_CLEANING[name]) for name in inputs}
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
                    arbiter = build_arbiter(args, inputs)
                elif turns and confirmed in turns:
                    # The turn blocks too. Keep the arbiter: the eyes may still be closed, and a fresh detector
                    # would read that as a new closure and turn again.
                    drain(client)
            elif now >= next_status:
                state = "FLYING" if flight.is_flying else "grounded"
                print("  ".join(f"{name}={values[name]:6.1f}" for name in inputs) + f"   {state}")
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
