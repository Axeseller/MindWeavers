# Phase 3 — Action policy and EEG readiness

> Superseded for runtime artifact control by `src/app.py` (`scripts/artifacts/vuelo6.py`), which
> uses `eeg.arbiter.InputArbiter` and per-session calibration. This document
> remains as the design record for the legacy `CommandMapper` path.

## Goal

Every basic skill can be bound to an EEG event by editing the mapper only, and short jaw clench toggles takeoff/land.

## Scope

1. **`src/mapping/commands.py`**
   - Extend `Action` with `BACK`, `LEFT`, `RIGHT`, `UP`, `DOWN`, `YAW_CW`, `YAW_CCW` (keeping `TAKEOFF`, `LAND`, `EMERGENCY`, `FORWARD`, `PHOTO`).
   - `CommandMapper.map()`:

| Event | Action |
|---|---|
| `JAW_SHORT` | `TAKEOFF` if grounded, `LAND` if flying (1.0 s shared cooldown) |
| `JAW_LONG` | `LAND` |
| `JAW_EMERGENCY` | `EMERGENCY` |
| `DOUBLE_BLINK` | `PHOTO` |

   - Movement actions exist but are not bound to an event yet. Binding a new gesture = add an `Event` + one mapper branch.

2. **`src/app.py`**
   - `apply_action()` dispatches movement and rotation actions through `tello.skills` (`ACTION_SKILLS` table) instead of calling controller methods directly.
   - The main loop keeps calling `apply_motion()` so bursts started by EEG are refreshed and end in hover.

3. **`docs/mapping.md`** updated to the new `JAW_SHORT` meaning.


## Safety

- The shared cooldown prevents one clench from taking off and immediately landing.
- `JAW_LONG` and `JAW_EMERGENCY` still land regardless of cooldown.
- Keyboard input bypasses the mapper and remains the safety override.

## Acceptance criteria

- `tests/test_command_mapper.py`: `JAW_SHORT` toggles by `is_flying`, cooldown blocks repeats, long/emergency/blink mappings unchanged.
- Dispatch test: every movement `Action` starts the matching skill on a dry-run controller.
- `python scripts/manual_mode.py --no-eeg` still runs.
