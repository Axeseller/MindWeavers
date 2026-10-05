# Phase 1 — Skill primitives

## Goal

Every basic skill is a reusable function with arguments (`seconds`, `speed`) so input data can be plugged in and tested without hardware.

## Scope

1. **Generic burst on `TelloController`** (`src/tello/controller.py`)
   - Replace the forward-only burst with stored state: active RC tuple `(lr, fb, ud, yv)` plus expiry time.
   - `start_burst(rc, seconds)` starts a bounded motion; returns `False` when grounded.
   - `apply_motion()` re-sends the active tuple until expiry, then hovers (zero RC). It must be called every loop tick (~10 Hz or faster) because Tello RC commands time out.
   - `cancel_burst()` clears motion; `land()`, `emergency_land()` and keyboard override use it.
   - `forward_burst()` becomes a thin call to `start_burst`.

2. **Named skills** (`src/tello/skills.py`)
   - Movement: `forward`, `back`, `left`, `right`, `up`, `down`.
   - Rotation: `yaw_clockwise`, `yaw_counterclockwise`.
   - State: `toggle_takeoff_land` (takeoff if grounded, land if flying; returns the action taken).
   - Shared helpers: `start_skill(controller, name, seconds, speed)` (non-blocking, for loops) and `run_skill(controller, name, seconds, speed)` (blocking, for scripts and tests).
   - Defaults: `seconds = 0.6`, `speed = RC_SPEED (50)`. Invalid input (`seconds <= 0`, `speed` outside 1–100, unknown name) raises `ValueError`.

## RC table

| Skill | Direction `(lr, fb, ud, yv)` |
|---|---|
| forward / back | `(0, +1, 0, 0)` / `(0, -1, 0, 0)` |
| right / left | `(+1, 0, 0, 0)` / `(-1, 0, 0, 0)` |
| up / down | `(0, 0, +1, 0)` / `(0, 0, -1, 0)` |
| yaw_clockwise / yaw_counterclockwise | `(0, 0, 0, +1)` / `(0, 0, 0, -1)` |

The direction is multiplied by `speed`. This matches `get_keyboard_command()` and `Tello/Mover.py`.

## Safety

- No RC is sent while `is_flying` is false.
- Landing always cancels the burst before `land()`.
- No new `djitellopy` call sites.

## Acceptance criteria

- `tests/test_tello_skills.py` passes in dry-run: each skill's RC tuple, speed scaling, burst expiry back to hover, grounded no-op, toggle behavior, argument validation.
- `python scripts/test_tello.py --dry-run` still runs end to end.
- `tests/test_jaw_detector.py` still passes.
