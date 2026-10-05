"""Basic Tello skills: bounded RC bursts plus SkillRunner for later EEG mapping.

Every movement skill takes `seconds` and `speed`, so recorded or live input can be passed straight in.
`SkillRunner.request(name)` is the single later entry point for keyboard or EEG.
"""

from __future__ import annotations

import threading
import time
from enum import Enum

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


HOLD_LEASE_S = 0.6
DRY_RUN_PROCESS_S = 1.5


class SkillKind(str, Enum):
    PROCESS = "PROCESS"
    CONTINUOUS = "CONTINUOUS"


PROCESS_SKILLS = {
    "takeoff": TelloController.takeoff,
    "land": TelloController.land,
}

SKILLS: dict[str, SkillKind] = {
    **{name: SkillKind.PROCESS for name in PROCESS_SKILLS},
    **{name: SkillKind.CONTINUOUS for name in MOVEMENT_SKILLS},
}


def skill_kind(name: str) -> SkillKind:
    if name not in SKILLS:
        raise ValueError(f"Unknown skill '{name}'. Choose from: {', '.join(SKILLS)}")
    return SKILLS[name]


class SkillRunner:
    """Gate between triggers and the controller. Call tick() every loop iteration."""

    def __init__(self, controller: TelloController, dry_run_process_s: float = DRY_RUN_PROCESS_S) -> None:
        self.controller = controller
        self.dry_run_process_s = dry_run_process_s
        self._worker: threading.Thread | None = None
        self._process_name: str | None = None
        self._process_error: Exception | None = None
        self._holding: str | None = None

    @property
    def busy(self) -> bool:
        return self._worker is not None and self._worker.is_alive()

    def request(self, name: str, speed: int = RC_SPEED, lease_s: float = HOLD_LEASE_S) -> bool:
        kind = skill_kind(name)
        if lease_s <= 0:
            raise ValueError(f"lease_s must be > 0, got {lease_s}")
        if self.busy:
            print(f"[skill] {name} ignored: {self._process_name} in progress")
            return False
        self._reap()
        if kind is SkillKind.PROCESS:
            return self._start_process(name)
        return self._hold(name, skill_rc(name, speed), speed, lease_s)

    def toggle_takeoff_land(self) -> str | None:
        name = "land" if self.controller.is_flying else "takeoff"
        return name if self.request(name) else None

    def tick(self) -> None:
        if self.busy:
            return
        self._reap()
        if self._holding and not self.controller.burst_active:
            self._holding = None
        self.controller.apply_motion()

    def _hold(self, name: str, rc: tuple[int, int, int, int], speed: int, lease_s: float) -> bool:
        continuing = self._holding == name and self.controller.burst_active
        if not self.controller.start_burst(rc, lease_s):
            return False
        if not continuing:
            print(f"--> {name} @ {speed}")
        self._holding = name
        return True

    def _start_process(self, name: str) -> bool:
        self.controller.cancel_burst()
        self._holding = None
        self._process_name = name
        self._process_error = None
        self._worker = threading.Thread(target=self._run_process, args=(name,), name=f"skill-{name}", daemon=True)
        self._worker.start()
        return True

    def _run_process(self, name: str) -> None:
        was_flying = self.controller.is_flying
        try:
            PROCESS_SKILLS[name](self.controller)
            if self.controller.dry_run and self.controller.is_flying != was_flying:
                time.sleep(self.dry_run_process_s)
        except Exception as exc:
            self._process_error = exc

    def _reap(self) -> None:
        worker = self._worker
        if worker is None or worker.is_alive():
            return
        worker.join()
        self._worker = None
        if self._process_error is not None:
            print(f"[skill] {self._process_name} failed: {self._process_error}")
        else:
            print(f"[skill] {self._process_name} done")
