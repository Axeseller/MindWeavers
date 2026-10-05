# Phase 5 — Skill runner: process and continuous skills

## Goal

Every basic skill is a procedure any trigger can call, and the jaw clench drives Manual Mode as a takeoff/land switch. The trigger for each movement is not decided yet, so attaching one must be a one-line change.

This phase replaces the bounded-burst helpers from Phase 1 (`start_skill`, `run_skill`, the per-skill wrappers) and the keyboard override from Phase 2 (`handle_keyboard`, `get_keyboard_command`).

## Two kinds of skill

| Kind | Skills | Behavior |
|---|---|---|
| Process | `takeoff`, `land` | Runs to completion on a worker thread. While it runs (`runner.busy`), **every request is rejected**; nothing is queued for later. No RC is sent. SDK errors are caught and printed, so the loop keeps running. |
| Continuous | `forward`, `back`, `left`, `right`, `up`, `down`, `yaw_clockwise`, `yaw_counterclockwise` | Moves **while the action persists**: each request keeps the RC tuple alive for `lease_s` more seconds. When requests stop, the lease runs out and the drone hovers. `release()` stops at once. Ignored while grounded or busy. |

Both live in `src/tello/skills.py`: `SKILLS` (name → kind), `PROCESS_SKILLS`, `MOVEMENT_SKILLS`, and `SkillRunner`.

## Attaching a trigger

```python
runner = SkillRunner(controller)

runner.request("takeoff")        # process: runs fully, rejects everything meanwhile
runner.request("forward")        # continuous: call it every tick while the action persists
runner.toggle_takeoff_land()     # switch: takeoff when grounded, land when flying
runner.tick()                    # once per loop iteration (~10 Hz or faster)
```

Existing triggers, both producing an `Action` that `ACTION_SKILLS` (`src/mapping/commands.py`) routes to a skill name:

| Trigger | Where | Binding |
|---|---|---|
| EEG jaw clench | `EegTrigger` (`src/eeg/trigger.py`) → `CommandMapper.map()` | `JAW_SHORT` = takeoff/land switch (1.0 s cooldown); `JAW_LONG` and `JAW_EMERGENCY` = land |
| Keyboard | `key_to_action()` | `Space` switch, `Q`/`E` takeoff/land, `W S A D Y U R T` movement |

To bind a new EEG gesture: add an `Event`, then one branch in `CommandMapper.map()` that returns the `Action`.

The keyboard lease is `HOLD_LEASE_S = 0.6`. It covers the ~0.5 s OS key-repeat delay, so a held key moves without gaps and the drone stops at most 0.6 s after release. A trigger polled every tick can pass a shorter `lease_s`.

## Entry points

- `scripts/manual_mode.py` — Manual Mode. Dry-run by default.
  - Clench switches takeoff/land using `jaw_takeoff_config()`, the same calibrated detector as `jaw_takeoff.py`. The keyboard drives the skills.
  - Flags: `--live`, `--no-video`, `--no-eeg`, `--threshold`, `--stream`.
  - Without a headset stream, dry-run continues keyboard-only; `--live` exits unless `--no-eeg` is given.
- `scripts/artifacts/fly.py` — supported multi-artifact runner. It uses `InputArbiter` and per-session calibration; see `scripts/artifacts/README.md`.
- `src/app.py` — main entry point; runs `scripts/artifacts/vuelo.py` (jaw takeoff/land, head forward, blink back) and translates the old app.py flags.
- `scripts/jaw_takeoff.py` — unchanged one-shot reference test.

## Safety

- A very long clench (`JAW_EMERGENCY`) lands normally. Motors are never cut from EEG; `emergency_land()` (motor stop via `tello.emergency()`) was removed.
- `Esc` / `Ctrl+C` wait for the running process skill to finish, then `controller.shutdown()` lands.
- Landing cancels any active movement.
- The switch fires on clench **release**: expect about 1 s between relaxing the jaw and the command (1 s feature window).

## Acceptance criteria

- `python -m unittest discover -s tests` passes (`test_tello_skills.py`, `test_command_mapper.py`, `test_eeg_trigger.py`, `test_jaw_detector.py`).
- `python scripts/manual_mode.py --no-eeg`: `Space` takes off; keys pressed during takeoff are ignored; holding `W` moves continuously; releasing hovers; `Space` lands.
- Live (spotter required): `python scripts/manual_mode.py --live` — clench takes off, each movement key moves the right way while held, clench lands.
