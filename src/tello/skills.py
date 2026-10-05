"""Basic Tello skills behind one entry point: `SkillRunner.request(name)`.

Two kinds of skill:
- PROCESS (takeoff, land): runs to completion on a worker thread. Every request made while it runs is rejected.
- CONTINUOUS (movement, yaw): moves while the trigger keeps requesting it, then hovers once the requests stop
  (lease expiry) or on `release()`.

Any trigger (keyboard, EEG event, IMU, ...) only has to call `runner.request(name)`.
"""

from __future__ import annotations

import threading
import time
from enum import Enum

from tello.controller import RC_SPEED, TelloController

MAX_RC_SPEED = 100
HOLD_LEASE_S = 0.6  # covers the ~0.5 s OS key-repeat delay so a held key moves without gaps
DRY_RUN_PROCESS_S = 1.5  # simulated takeoff/land time so dry-run shows the busy window


class SkillKind(str, Enum):
    PROCESS = "PROCESS"
    CONTINUOUS = "CONTINUOUS"


# Process skills: one controller call that must finish before anything else is accepted.
PROCESS_SKILLS = {
    "takeoff": TelloController.takeoff,
    "land": TelloController.land,
}

# Continuous skills: unit direction as (lr, fb, ud, yv), multiplied by speed.
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

SKILLS: dict[str, SkillKind] = {
    **{name: SkillKind.PROCESS for name in PROCESS_SKILLS},
    **{name: SkillKind.CONTINUOUS for name in MOVEMENT_SKILLS},
}


def skill_kind(name: str) -> SkillKind:
    if name not in SKILLS:
        raise ValueError(f"Unknown skill '{name}'. Choose from: {', '.join(SKILLS)}")
    return SKILLS[name]


def skill_rc(name: str, speed: int = RC_SPEED) -> tuple[int, int, int, int]:
    if name not in MOVEMENT_SKILLS:
        raise ValueError(f"Unknown movement skill '{name}'. Choose from: {', '.join(MOVEMENT_SKILLS)}")
    if not 1 <= speed <= MAX_RC_SPEED:
        raise ValueError(f"speed must be 1-{MAX_RC_SPEED}, got {speed}")
    lr, fb, ud, yv = MOVEMENT_SKILLS[name]
    return lr * speed, fb * speed, ud * speed, yv * speed


class SkillRunner:
    """Single gate between triggers and the controller. Call `tick()` every loop iteration (~10 Hz or faster)."""

    def __init__(self, controller: TelloController, dry_run_process_s: float = DRY_RUN_PROCESS_S) -> None:
        self.controller = controller
        self.dry_run_process_s = dry_run_process_s
        self._worker: threading.Thread | None = None
        self._process_name: str | None = None
        self._process_error: Exception | None = None
        self._rejected: set[str] = set()
        self._holding: str | None = None

    @property
    def busy(self) -> bool:
        """True while a process skill runs; every request is rejected meanwhile."""
        return self._worker is not None and self._worker.is_alive()

    def request(self, name: str, speed: int = RC_SPEED, lease_s: float = HOLD_LEASE_S) -> bool:
        """Trigger a skill. Process: start it once. Continuous: keep moving for `lease_s` more seconds."""
        kind = skill_kind(name)
        rc = skill_rc(name, speed) if kind is SkillKind.CONTINUOUS else None
        if lease_s <= 0:
            raise ValueError(f"lease_s must be > 0, got {lease_s}")
        if self.busy:
            if name not in self._rejected:
                print(f"[skill] {name} ignored: {self._process_name} in progress")
                self._rejected.add(name)
            return False
        self._reap()
        if kind is SkillKind.PROCESS:
            return self._start_process(name)
        return self._hold(name, rc, speed, lease_s)

    def toggle_takeoff_land(self) -> str | None:
        """Switch: take off when grounded, land when flying. Returns the skill started, or None if rejected."""
        name = "land" if self.controller.is_flying else "takeoff"
        return name if self.request(name) else None

    def release(self) -> None:
        """Stop the current continuous skill now; the next tick hovers."""
        self.controller.cancel_burst()

    def tick(self) -> None:
        """Refresh the active motion or hover. Sends nothing while a process skill runs."""
        if self.busy:
            return
        self._reap()
        if self._holding and not self.controller.burst_active:
            print("--> hover")
            self._holding = None
        self.controller.apply_motion()

    def wait_idle(self, timeout: float | None = None) -> bool:
        """Block until the running process skill finishes. Returns False on timeout."""
        if self._worker is not None:
            self._worker.join(timeout)
        if self.busy:
            return False
        self._reap()
        return True

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
        self._rejected = set()
        self._worker = threading.Thread(target=self._run_process, args=(name,), name=f"skill-{name}", daemon=True)
        self._worker.start()
        return True

    def _run_process(self, name: str) -> None:
        was_flying = self.controller.is_flying
        try:
            PROCESS_SKILLS[name](self.controller)
            if self.controller.dry_run and self.controller.is_flying != was_flying:
                time.sleep(self.dry_run_process_s)
        except Exception as exc:  # SDK errors must not kill the control loop
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
