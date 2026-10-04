from __future__ import annotations

from enum import Enum


class Event(str, Enum):
    JAW_SHORT = "JAW_SHORT"
    JAW_LONG = "JAW_LONG"
    JAW_EMERGENCY = "JAW_EMERGENCY"
    DOUBLE_BLINK = "DOUBLE_BLINK"


class Action(str, Enum):
    TAKEOFF = "TAKEOFF"
    LAND = "LAND"
    EMERGENCY = "EMERGENCY"
    FORWARD = "FORWARD"
    PHOTO = "PHOTO"


class CommandMapper:
    """Translate detector events into one Tello action with a shared cooldown."""

    def __init__(self, cooldown_s: float = 1.0) -> None:
        self.cooldown_s = cooldown_s
        self._next_flight_at = 0.0

    def map(self, event: str, is_flying: bool, now: float) -> str | None:
        if event == Event.DOUBLE_BLINK:
            return Action.PHOTO
        if event == Event.JAW_EMERGENCY:
            return Action.EMERGENCY
        if event == Event.JAW_LONG:
            return Action.LAND
        if event != Event.JAW_SHORT:
            return None
        if now < self._next_flight_at:
            return None
        self._next_flight_at = now + self.cooldown_s
        return Action.FORWARD if is_flying else Action.TAKEOFF
