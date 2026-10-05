# Phase 2 — Manual Mode

## Goal

A free keyboard controller (`scripts/manual_mode.py`) that flies every basic skill through `TelloController`, replacing direct SDK use in `Tello/Mover.py`.

## Scope

- Entry script in `scripts/`, imports `_paths`, then `tello.controller` and `tello.skills`.
- CLI:
  - default: dry-run (no socket, prints commands)
  - `--live`: connect to the real Tello
  - `--no-video`: skip the camera stream (the OpenCV window still opens to capture keys)
- Keyboard layout (same as `get_keyboard_command()`):

| Key | Action |
|---|---|
| `Q` / `E` | Takeoff / Land |
| `Space` | Takeoff/Land toggle (`toggle_takeoff_land`) |
| `W` / `S` | Forward / Back |
| `A` / `D` | Left / Right |
| `Y` / `U` | Up / Down |
| `R` / `T` | Counter-clockwise / Clockwise |
| `Esc` | Exit (lands through `shutdown()`) |

- Loop per tick: `show_video()` -> handle key -> `apply_motion()` when no movement key is held -> short sleep. Holding a key moves continuously; releasing it hovers.

## Lifecycle and safety

1. Build `TelloController(dry_run=not args.live)`.
2. `connect()`; on failure (no drone, battery < 20%) call `shutdown()` and exit with code 1.
3. Main loop inside `try`; `KeyboardInterrupt` exits cleanly.
4. `finally: controller.shutdown()` lands and releases video.

## Acceptance criteria

- `python scripts/manual_mode.py` opens the window in dry-run and prints takeoff/land; movement keys only act after takeoff.
- `Esc` and `Ctrl+C` both reach `shutdown()`.
- Live smoke test (Phase 4): takeoff, one short press per axis and yaw direction, land.
