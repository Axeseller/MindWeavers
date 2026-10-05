"""Basic Tello skills: bounded RC bursts plus the takeoff/land toggle.

Every movement skill takes `seconds` and `speed`, so recorded or live input can be passed straight in.
"""

from __future__ import annotations

import time

from tello.controller import FORWARD_BURST_SECONDS, RC_SPEED, TelloController

DEFAULT_SKILL_SECONDS = FORWARD_BURST_SECONDS
MAX_RC_SPEED = 100
SKILL_TICK_S = 0.05

# Unit direction per skill as (lr, fb, ud, yv); multiplied by speed.
MOVEMENT_SKILLS: dict[str, tuple[int, int, int, int]] = {
    "forward": (0, 1, 0, 0),
    "back": (0, -1, 0, 0),
    "right": (1, 0, 0, 0),
    "left": (-1, 0, 0, 0),
    "up": (0, 0, 1, 0),
    "down": (0, 0, -1, 0),
    "yaw_clockwise": (0, 0, 0, 1),
    "yaw_counterclockwise": (0, 0, 0, -1),
}


def skill_rc(name: str, speed: int = RC_SPEED) -> tuple[int, int, int, int]:
    if name not in MOVEMENT_SKILLS:
        raise ValueError(f"Unknown skill '{name}'. Choose from: {', '.join(MOVEMENT_SKILLS)}")
    if not 1 <= speed <= MAX_RC_SPEED:
        raise ValueError(f"speed must be 1-{MAX_RC_SPEED}, got {speed}")
    lr, fb, ud, yv = MOVEMENT_SKILLS[name]
    return lr * speed, fb * speed, ud * speed, yv * speed


def start_skill(
    controller: TelloController,
    name: str,
    seconds: float = DEFAULT_SKILL_SECONDS,
    speed: int = RC_SPEED,
) -> bool:
    """Non-blocking: start the burst; the caller's loop must call controller.apply_motion()."""
    if seconds <= 0:
        raise ValueError(f"seconds must be > 0, got {seconds}")
    rc = skill_rc(name, speed)
    started = controller.start_burst(rc, seconds)
    if started:
        print(f"--> {name} {seconds:.2f}s @ {speed}")
    return started


def run_skill(
    controller: TelloController,
    name: str,
    seconds: float = DEFAULT_SKILL_SECONDS,
    speed: int = RC_SPEED,
) -> bool:
    """Blocking: run the burst to completion, then send one hover command."""
    if not start_skill(controller, name, seconds, speed):
        return False
    while controller.burst_active:
        controller.apply_motion()
        time.sleep(SKILL_TICK_S)
    controller.hover()
    return True


def toggle_takeoff_land(controller: TelloController) -> str:
    """Take off when grounded, land when flying. Returns "TAKEOFF" or "LAND"."""
    if controller.is_flying:
        controller.land()
        return "LAND"
    controller.takeoff()
    return "TAKEOFF"


def forward(controller: TelloController, seconds: float = DEFAULT_SKILL_SECONDS, speed: int = RC_SPEED) -> bool:
    return start_skill(controller, "forward", seconds, speed)


def back(controller: TelloController, seconds: float = DEFAULT_SKILL_SECONDS, speed: int = RC_SPEED) -> bool:
    return start_skill(controller, "back", seconds, speed)


def right(controller: TelloController, seconds: float = DEFAULT_SKILL_SECONDS, speed: int = RC_SPEED) -> bool:
    return start_skill(controller, "right", seconds, speed)


def left(controller: TelloController, seconds: float = DEFAULT_SKILL_SECONDS, speed: int = RC_SPEED) -> bool:
    return start_skill(controller, "left", seconds, speed)


def up(controller: TelloController, seconds: float = DEFAULT_SKILL_SECONDS, speed: int = RC_SPEED) -> bool:
    return start_skill(controller, "up", seconds, speed)


def down(controller: TelloController, seconds: float = DEFAULT_SKILL_SECONDS, speed: int = RC_SPEED) -> bool:
    return start_skill(controller, "down", seconds, speed)


def yaw_clockwise(controller: TelloController, seconds: float = DEFAULT_SKILL_SECONDS, speed: int = RC_SPEED) -> bool:
    return start_skill(controller, "yaw_clockwise", seconds, speed)


def yaw_counterclockwise(
    controller: TelloController, seconds: float = DEFAULT_SKILL_SECONDS, speed: int = RC_SPEED
) -> bool:
    return start_skill(controller, "yaw_counterclockwise", seconds, speed)
