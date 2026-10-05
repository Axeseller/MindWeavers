from __future__ import annotations

import time
from pathlib import Path

import cv2
import numpy as np

MIN_BATTERY_PERCENT = 20
RC_SPEED = 50
FORWARD_BURST_SECONDS = 0.6
VIDEO_SIZE = (640, 480)
WINDOW_NAME = "Mind Weavers - Tello"


def get_keyboard_command(key: int) -> tuple[str, tuple[int, int, int, int]]:
    """Map an OpenCV keycode to a command, same layout as DroneOps Mover.py."""
    lr, fb, ud, yv = 0, 0, 0, 0
    if key in (ord("q"), ord("Q")):
        return "TAKEOFF", (0, 0, 0, 0)
    if key in (ord("e"), ord("E")):
        return "LAND", (0, 0, 0, 0)
    if key in (ord("a"), ord("A")):
        lr = -RC_SPEED
    elif key in (ord("d"), ord("D")):
        lr = RC_SPEED
    elif key in (ord("w"), ord("W")):
        fb = RC_SPEED
    elif key in (ord("s"), ord("S")):
        fb = -RC_SPEED
    elif key in (ord("y"), ord("Y")):
        ud = RC_SPEED
    elif key in (ord("u"), ord("U")):
        ud = -RC_SPEED
    elif key in (ord("r"), ord("R")):
        yv = -RC_SPEED
    elif key in (ord("t"), ord("T")):
        yv = RC_SPEED
    return "FLIGHT", (lr, fb, ud, yv)


def print_keyboard_help() -> None:
    print("\n" + "=" * 45)
    print("  KEYBOARD OVERRIDE (focus the video window)")
    print("=" * 45)
    print(" [Q] takeoff   [E] land   [ESC] exit")
    print(" [W/S] forward/back   [A/D] left/right")
    print(" [Y/U] up/down        [R/T] yaw")
    print("=" * 45 + "\n")


class TelloController:
    """Only module that talks to the drone. Dry-run prints and never opens a socket."""

    def __init__(self, dry_run: bool = False) -> None:
        self.dry_run = dry_run
        self.is_flying = False
        self._tello: object | None = None
        self._frame_read: object | None = None
        self._burst_until = 0.0
        self._burst_rc: tuple[int, int, int, int] = (0, 0, 0, 0)

    def connect(self, with_video: bool = True) -> bool:
        if self.dry_run:
            print("[dry-run] Tello connect skipped")
            return True
        return self._connect_hardware(with_video)

    def takeoff(self) -> None:
        if self.is_flying:
            return
        print("--> Takeoff")
        if not self.dry_run and self._tello is not None:
            self._tello.takeoff()
        self.is_flying = True

    def land(self) -> None:
        if not self.is_flying and self.dry_run:
            print("--> Land (already grounded)")
            return
        print("--> Land")
        self.cancel_burst()
        if not self.dry_run and self._tello is not None:
            self._tello.send_rc_control(0, 0, 0, 0)
            self._tello.land()
        self.is_flying = False

    def emergency_land(self) -> None:
        print("--> Emergency land")
        self.cancel_burst()
        if not self.dry_run and self._tello is not None:
            try:
                self._tello.send_rc_control(0, 0, 0, 0)
                self._tello.emergency()
            except Exception:
                self._tello.land()
        self.is_flying = False

    def hover(self) -> None:
        if self.is_flying and time.monotonic() >= self._burst_until:
            self.send_rc(0, 0, 0, 0)

    @property
    def burst_active(self) -> bool:
        return self.is_flying and time.monotonic() < self._burst_until

    @property
    def burst_rc(self) -> tuple[int, int, int, int]:
        return self._burst_rc if self.burst_active else (0, 0, 0, 0)

    def start_burst(self, rc: tuple[int, int, int, int], seconds: float) -> bool:
        """Hold one RC tuple for `seconds`; apply_motion() must be called every tick to keep it alive."""
        if not self.is_flying:
            return False
        self._burst_rc = rc
        self._burst_until = time.monotonic() + seconds
        self.send_rc(*rc)
        return True

    def cancel_burst(self) -> None:
        self._burst_until = 0.0
        self._burst_rc = (0, 0, 0, 0)

    def forward_burst(self) -> None:
        if self.start_burst((0, RC_SPEED, 0, 0), FORWARD_BURST_SECONDS):
            print("--> Forward burst")

    def apply_motion(self) -> None:
        if self.burst_active:
            self.send_rc(*self._burst_rc)
        else:
            self.hover()

    def send_rc(self, lr: int, fb: int, ud: int, yv: int) -> None:
        if not self.is_flying:
            return
        if not self.dry_run and self._tello is not None:
            self._tello.send_rc_control(lr, fb, ud, yv)

    def take_photo(self, output_dir: Path) -> Path | None:
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"photo_{int(time.time())}.jpg"
        if self.dry_run:
            print(f"[dry-run] Photo -> {path}")
            return path
        frame = self._raw_frame()
        if frame is None:
            print("--> Photo skipped (no frame)")
            return None
        cv2.imwrite(str(path), frame)
        print(f"--> Photo saved {path}")
        return path

    def show_video(self) -> int:
        """Draw the latest frame and return the OpenCV keycode (255 if none)."""
        frame = self._display_frame()
        cv2.imshow(WINDOW_NAME, cv2.resize(frame, VIDEO_SIZE))
        return cv2.waitKey(1) & 0xFF

    def handle_keyboard(self, key: int) -> str:
        """Apply a keypress. Returns exit, override, or idle."""
        if key == 255:
            return "idle"
        if key == 27:
            print("\n[!] Emergency exit from keyboard.")
            return "exit"
        command, rc = get_keyboard_command(key)
        if command == "TAKEOFF":
            self.takeoff()
        elif command == "LAND":
            self.land()
        elif command == "FLIGHT" and any(rc):
            self.cancel_burst()
            self.send_rc(*rc)
            return "override"
        return "idle"

    def shutdown(self) -> None:
        print("\nShutting down Tello...")
        if self.dry_run:
            self.is_flying = False
            cv2.destroyAllWindows()
            return
        self._shutdown_hardware()

    def _connect_hardware(self, with_video: bool) -> bool:
        from djitellopy import Tello

        tello = Tello()
        print("Connecting to Tello...")
        tello.connect()
        battery = tello.get_battery()
        print(f"Battery: {battery}%")
        if battery < MIN_BATTERY_PERCENT:
            print("Battery too low for a safe flight. Charge and retry.")
            return False
        if with_video:
            print("Starting video stream...")
            tello.streamon()
            time.sleep(2)
            self._frame_read = tello.get_frame_read()
        self._tello = tello
        return True

    def _raw_frame(self):
        if self._frame_read is None:
            return None
        return self._frame_read.frame

    def _display_frame(self):
        raw = self._raw_frame()
        if raw is None:
            blank = np.zeros((VIDEO_SIZE[1], VIDEO_SIZE[0], 3), dtype=np.uint8)
            cv2.putText(blank, "dry-run / no video", (80, 250), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            return blank
        return cv2.cvtColor(raw, cv2.COLOR_BGR2RGB)

    def _shutdown_hardware(self) -> None:
        tello = self._tello
        try:
            if tello is not None:
                tello.send_rc_control(0, 0, 0, 0)
                tello.land()
        except Exception:
            pass
        try:
            if tello is not None:
                tello.streamoff()
        except Exception:
            pass
        cv2.destroyAllWindows()
        self.is_flying = False
        self._tello = None
