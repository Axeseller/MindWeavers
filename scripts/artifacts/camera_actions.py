"""Camera actions shared by blink.py, cerrar_ojos.py and camera.py."""

from __future__ import annotations

from pathlib import Path

from tello.controller import TelloController

PHOTO_DIR = Path(__file__).resolve().parents[2] / "data" / "recordings"


def toggle_camera(controller: TelloController) -> None:
    """Closing the eyes: camera on if it was off, off if it was on."""
    if controller.camera_on:
        controller.stop_camera()
    else:
        controller.start_camera()


def take_photo(controller: TelloController) -> None:
    """Blink: photo only while the camera is on."""
    if controller.camera_on:
        controller.take_photo(PHOTO_DIR)
    else:
        print("Camera is off: close your eyes for 1.5 s to turn it on.")
