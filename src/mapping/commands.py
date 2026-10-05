from __future__ import annotations

from enum import Enum

KEY_NONE = 255
KEY_ESC = 27
KEY_SPACE = 32


class Event(str, Enum):
    JAW_SHORT = "JAW_SHORT"
    JAW_LONG = "JAW_LONG"
    JAW_EMERGENCY = "JAW_EMERGENCY"
    DOUBLE_BLINK = "DOUBLE_BLINK"
    ROTATE_CW = "ROTATE_CW"
    ROTATE_CCW = "ROTATE_CCW"
    BLINK = "BLINK"
    EYES_CLOSED = "EYES_CLOSED"
    EYES_OPENED = "EYES_OPENED"
    HAPPY = "HAPPY"
    ENOJADO = "ENOJADO"
    PUNO_IZQ = "PUNO_IZQ"
    PUNO_DER = "PUNO_DER"
    BRAZO_IZQ = "BRAZO_IZQ"
    BRAZO_ARRIBA = "BRAZO_ARRIBA"
    CUELLO_IZQ = "CUELLO_IZQ"
    CUELLO_DER = "CUELLO_DER"
    GIRO_IMAG_IZQ = "GIRO_IMAG_IZQ"
    GIRO_IMAG_DER = "GIRO_IMAG_DER"


class Action(str, Enum):
    TAKEOFF = "TAKEOFF"
    LAND = "LAND"
    EMERGENCY = "EMERGENCY"
    FORWARD = "FORWARD"
    BACK = "BACK"
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    UP = "UP"
    DOWN = "DOWN"
    YAW_CW = "YAW_CW"
    YAW_CCW = "YAW_CCW"
    PHOTO = "PHOTO"


ACTION_SKILLS: dict[Action, str] = {
    Action.FORWARD: "forward",
    Action.BACK: "back",
    Action.LEFT: "left",
    Action.RIGHT: "right",
    Action.UP: "up",
    Action.DOWN: "down",
    Action.YAW_CW: "yaw_clockwise",
    Action.YAW_CCW: "yaw_counterclockwise",
}

KEY_ACTIONS: dict[str, Action] = {
    "q": Action.TAKEOFF,
    "e": Action.LAND,
    "w": Action.FORWARD,
    "s": Action.BACK,
    "a": Action.LEFT,
    "d": Action.RIGHT,
    "y": Action.UP,
    "u": Action.DOWN,
    "r": Action.YAW_CCW,
    "t": Action.YAW_CW,
}


def key_to_action(key: int, is_flying: bool) -> Action | None:
    """Map an OpenCV keycode to an Action. Space switches takeoff/land."""
    if key == KEY_SPACE:
        return Action.LAND if is_flying else Action.TAKEOFF
    if not 0 <= key < KEY_NONE:
        return None
    return KEY_ACTIONS.get(chr(key).lower())


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
        if event == Event.ROTATE_CW:
            return Action.YAW_CW
        if event == Event.ROTATE_CCW:
            return Action.YAW_CCW
        if event != Event.JAW_SHORT:
            return None
        if now < self._next_flight_at:
            return None
        self._next_flight_at = now + self.cooldown_s
        return Action.LAND if is_flying else Action.TAKEOFF
