from __future__ import annotations

import time
from pathlib import Path

import cv2
import numpy as np

MIN_BATTERY_PERCENT = 20
RC_SPEED = 50
VIDEO_SIZE = (640, 480)
VIDEO_FPS = 20
WINDOW_NAME = "Mind Weavers - Tello"


def print_keyboard_help() -> None:
    print("\n" + "=" * 45)
    print("  KEYBOARD (focus the video window)")
    print("=" * 45)
    print(" [SPACE] takeoff/land switch   [ESC] exit")
    print(" [Q] takeoff   [E] land")
    print(" [W/S] forward/back   [A/D] left/right")
    print(" [Y/U] up/down        [R/T] yaw")
    print(" Hold a movement key to keep moving.")
    print("=" * 45 + "\n")


class TelloController:
    """Only module that talks to the drone. Dry-run prints and never opens a socket."""

    def __init__(self, dry_run: bool = False) -> None:
        self.dry_run = dry_run
        self.is_flying = False
        self._tello: object | None = None
        self._frame_read: object | None = None
        self._camera_on = False
        self._recording = False
        self._video_writer: cv2.VideoWriter | None = None
        self._video_path: Path | None = None
        self._burst_until = 0.0
        self._burst_rc: tuple[int, int, int, int] = (0, 0, 0, 0)

    @property
    def camera_on(self) -> bool:
        return self._frame_read is not None or (self.dry_run and self._camera_on)

    @property
    def is_recording(self) -> bool:
        return self._recording

    def connect(self, with_video: bool = True) -> bool:
        if self.dry_run:
            print("[dry-run] Tello connect skipped")
            if with_video:
                self.start_camera()
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

    def start_camera(self) -> bool:
        if self.camera_on:
            return True
        if self.dry_run:
            print("[dry-run] Camera stream on")
            self._camera_on = True
            return True
        if self._tello is None:
            print("--> Camera skipped (not connected)")
            return False
        print("Starting video stream...")
        self._tello.streamon()
        time.sleep(2)
        self._frame_read = self._tello.get_frame_read()
        self._camera_on = True
        return True

    def stop_camera(self) -> None:
        """Stop any recording and turn the video stream off."""
        self.stop_recording()
        if not self.camera_on:
            return
        print("--> Camera off")
        if not self.dry_run and self._tello is not None:
            self._tello.streamoff()
        self._frame_read = None
        self._camera_on = False

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

    def start_recording(self, output_dir: Path) -> Path | None:
        if self._recording:
            return self._video_path
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"video_{int(time.time())}.mp4"
        if self.dry_run:
            print(f"[dry-run] Video start -> {path}")
            self._recording = True
            self._video_path = path
            return path
        return self._open_video_writer(path)

    def record_frame(self) -> None:
        if not self._recording or self.dry_run or self._video_writer is None:
            return
        frame = self._raw_frame()
        if frame is not None:
            self._video_writer.write(frame)

    def stop_recording(self) -> Path | None:
        if not self._recording:
            return None
        path = self._video_path
        if self._video_writer is not None:
            self._video_writer.release()
        self._video_writer = None
        self._recording = False
        self._video_path = None
        print(f"--> Video saved {path}")
        return path

    def _open_video_writer(self, path: Path) -> Path | None:
        frame = self._raw_frame()
        if frame is None:
            print("--> Video skipped (no frame)")
            return None
        height, width = frame.shape[:2]
        writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), VIDEO_FPS, (width, height))
        if not writer.isOpened():
            print("--> Video skipped (writer failed)")
            return None
        self._video_writer = writer
        self._recording = True
        self._video_path = path
        print(f"--> Video start {path}")
        return path

    def show_video(self) -> int:
        """Draw the latest frame and return the OpenCV keycode (255 if none)."""
        frame = self._display_frame()
        cv2.imshow(WINDOW_NAME, cv2.resize(frame, VIDEO_SIZE))
        return cv2.waitKey(1) & 0xFF

    def shutdown(self) -> None:
        print("\nShutting down Tello...")
        self.stop_recording()
        if self.dry_run:
            self.is_flying = False
            self._camera_on = False
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
        self._tello = tello
        if with_video:
            return self.start_camera()
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
        self._camera_on = False
        self._frame_read = None
        self._tello = None
