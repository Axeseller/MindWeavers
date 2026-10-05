# `jaw_takeoff.py` execution and skill-building research

## Purpose and scope

`scripts/jaw_takeoff.py` is a one-shot, EEG-triggered mission:

```text
Unicorn LSL samples
  -> 1-second EEG window
  -> filtering and jaw-RMS feature
  -> jaw detector
  -> JAW_SHORT event
  -> take off, hover, land
```

It defaults to a safe dry run. `--live` is required before it talks to a real Tello.

This document separates the code that is required to create drone skills from supporting calibration, reference, and legacy code. It describes the code as it exists; it does not propose or create a skill implementation.

## Execution path

1. **Import setup — `scripts/_paths.py`**
   - Adds `<repo>/src` to `sys.path`, allowing scripts to import `eeg`, `lsl`, `mapping`, and `tello`.
   - Required by standalone scripts in `scripts/`; it contains no flight or EEG behavior.

2. **Argument parsing — `parse_args()` in `scripts/jaw_takeoff.py`**
   - `--live`: opts into physical-drone control; absent means dry run.
   - `--stream`: selects the LSL source; default is `UnicornRecorderRawDataLSLStream`.
   - `--threshold`: sets the jaw-RMS entry threshold; default is `40.0`.
   - `--hover-seconds`: controls the local mission’s hover duration; default is eight seconds.

3. **Drone connection — `TelloController.connect(with_video=False)`**
   - `TelloController` is created with `dry_run=not args.live`.
   - In dry run it returns successfully without opening a socket. In live mode it connects through `djitellopy`, checks battery, and rejects batteries below 20%.
   - Video is deliberately disabled: this mission needs no camera stream or keyboard window.

4. **Headset connection — `LslClient.connect()`**
   - Resolves a named Unicorn raw LSL stream for up to eight seconds.
   - Failure closes the controller and exits. The selected stream must publish the expected EEG columns.

5. **Signal-to-event loop**
   - `pull_chunk(timeout=0.05)` receives samples and appends them to the client’s one-second ring buffer.
   - The script waits for at least `SAMPLE_RATE` samples (250), then processes the window.
   - `preprocess_window()` removes 60 Hz noise and band-passes EEG columns 0–7 to 1–40 Hz.
   - `extract_features()` derives jaw RMS from 15–40 Hz energy across those eight EEG columns.
   - `ArtifactDetector.update(jaw_rms, 0.0, time.monotonic())` turns the measurement into events. Blink data is intentionally passed as zero.
   - When `Event.JAW_SHORT` appears, the script calls `fly_once()` and ends its loop.

6. **One-shot mission — `fly_once()`**
   - Calls `takeoff()`.
   - Calls `hover()` every 0.1 seconds until the requested duration expires. This refreshes zero RC commands while airborne.
   - Calls `land()`.

7. **Cleanup**
   - The `finally` block closes LSL and calls `controller.shutdown()` after normal completion or `Ctrl+C`.
   - Hardware shutdown attempts zero RC, landing, video shutdown (if used), and OpenCV window cleanup.

## Required components for basic drone skills

| Component | Why it is required | Reusable contract |
|---|---|---|
| `src/tello/controller.py` — `TelloController` | It is the only current wrapper around the physical Tello SDK and centralizes dry-run behavior, battery gating, state, shutdown, and RC commands. New skills should not add direct `djitellopy` call sites. | Construct with `dry_run`; call `connect()`, then use `takeoff()`, `land()`, `send_rc(lr, fb, ud, yv)`, `hover()`, and always `shutdown()`. |
| `TelloController.is_flying` | Prevents ground-only commands from being issued as flight movements and supports takeoff/land state behavior. | Local software state only; treat it as a guard, not confirmed drone telemetry. |
| `TelloController.send_rc()` | This is the primitive for forward/back, left/right, up/down, and yaw. Its tuple is `(left_right, forward_back, up_down, yaw)`. | A named movement skill should map to one RC tuple, run for a bounded duration while flying, then send/refresh `(0, 0, 0, 0)`. |
| `scripts/_paths.py` | Makes `src` imports work from a script entry point. | Import it for new files placed in `scripts/`; package code under `src` does not need it. |
| `try`/`finally` controller lifecycle | Landing/releasing resources is the safety boundary when the user interrupts or the skill fails. | `connect()` before use; `shutdown()` in `finally`. |

### Existing mappings for the requested basic skills

`get_keyboard_command()` in `src/tello/controller.py` already defines the RC direction conventions at `RC_SPEED = 50`:

| Skill | RC tuple |
|---|---|
| Forward / back | `(0, +50, 0, 0)` / `(0, -50, 0, 0)` |
| Right / left | `(+50, 0, 0, 0)` / `(-50, 0, 0, 0)` |
| Up / down | `(0, 0, +50, 0)` / `(0, 0, -50, 0)` |
| Clockwise / counter-clockwise | `(0, 0, 0, +50)` / `(0, 0, 0, -50)` |
| Takeoff / land | `takeoff()` / `land()`; choose from `is_flying` when defining a toggle-style skill |

`forward_burst()` is the only current named motion skill. It demonstrates a 0.6-second bounded forward action. `apply_motion()` refreshes it until the burst ends, then hovers. The other basic skills should reuse the lower-level RC contract rather than duplicate the legacy SDK calls.

## Required only for EEG-controlled skills

| Component | Important behavior | Reuse decision |
|---|---|---|
| `src/lsl/client.py` — `LslClient` | Resolves Unicorn LSL, exposes chunks, and retains a one-second buffer at 250 Hz. It assumes the first eight columns are EEG. | Required for live EEG input; reusable unchanged for skills driven by the same headset stream. |
| `src/eeg/preprocess.py` | Filters EEG columns 0–7; leaves other stream columns unchanged. `extract_features()` returns `(jaw_rms, blink_amp)`. | Required for the current jaw/blink recognition pipeline. Reuse before detector updates. |
| `src/eeg/detectors.py` — `ArtifactDetector` | Applies threshold, hysteresis, duration classification, and refractory time to features. | Reusable event state machine; use a dedicated `DetectorConfig` when a skill needs materially different gesture timing. |
| `jaw_takeoff_config()` | Takes effect only in the one-shot script: threshold 40 by default, short jaw duration 0.5–2.0 s, and blink detection disabled. | Reuse specifically for the takeoff gesture, not as the universal multi-skill configuration. |
| `src/mapping/commands.py` — `Event` | Stable event vocabulary: `JAW_SHORT`, `JAW_LONG`, `JAW_EMERGENCY`, and `DOUBLE_BLINK`. | Reuse for a shared interface between detectors and skill/action policy. |

### Jaw detector details that affect reliability

- A jaw gesture starts at `jaw_rms >= threshold` and ends only below `threshold * 0.6`. This hysteresis prevents a noisy clench from repeatedly starting/stopping.
- With `jaw_takeoff_config()`, release after 0.5–2.0 seconds emits `JAW_SHORT`. A shorter spike is ignored. A gesture of two seconds or more emits `JAW_LONG`; a held gesture of ten seconds emits `JAW_EMERGENCY`.
- Event classification happens on release, not at gesture start.
- The detector waits 0.8 seconds after an emitted event before accepting another.
- The takeoff script discards `blink_amp`, and its configuration sets blink threshold to infinity. Therefore a double blink cannot affect `jaw_takeoff.py`.
- The first approximately one second after starting has no detection because the LSL window must fill.

## Reusable multi-skill integration

`jaw_takeoff.py` intentionally bypasses the general action mapper. For a continuous EEG controller, the reusable integration is in `src/app.py`:

1. `process_eeg()` performs LSL pull, preprocessing, feature extraction, detection, and event collection.
2. `CommandMapper.map(event, is_flying, now)` turns an event into one `Action`, including a one-second cooldown for jaw flight actions.
3. `apply_action()` dispatches that action to `TelloController`.

Current policy:

| Event | Existing mapped action |
|---|---|
| `JAW_SHORT` | `TAKEOFF` when grounded; `FORWARD` when flying |
| `JAW_LONG` | `LAND` |
| `JAW_EMERGENCY` | `EMERGENCY` |
| `DOUBLE_BLINK` | `PHOTO` |

For future artifact-controlled skills, this policy layer is the reusable place to add action selection and cooldown rules. It keeps detector logic independent of flight behavior. Extending `Event`, `Action`, the mapper, and `apply_action()` together is necessary when a new gesture should produce a new named action.

## Supporting, but not runtime-required

| File | Role | When it matters |
|---|---|---|
| `scripts/record_baseline.py` | Records labeled raw LSL samples to `data/baselines`. | Run before live EEG flights to collect participant/session-specific rest and gesture data. |
| `scripts/analyze_baselines.py` | Replays the same filter/feature/detector path over baseline CSVs and suggests a jaw threshold. | Use to select `--threshold`; it is not read by `jaw_takeoff.py` at runtime. |
| `tests/test_jaw_detector.py` | Checks rest, valid/invalid clench durations, hysteresis, and disabled blink behavior. | Reuse its feature-free detector tests when changing timing or thresholds. The six current tests pass. |
| `docs/hardware.md` | Documents Unicorn setup, Tello Wi-Fi, LSL stream name, and flight sequence. | Required operational reference for hardware tests, not an imported dependency. |
| `requirements.txt` | Lists `djitellopy`, `opencv-python`, `pylsl`, `numpy`, and `scipy`. | Required environment setup before live use. `opencv-python` is still imported by the controller even with video disabled. |

## Reference or legacy code: do not build new skills on it

- `Tello/Mover.py` directly uses `djitellopy` and duplicates keyboard-to-RC behavior. It is a useful directional reference, but it is not imported by `jaw_takeoff.py` and has no dry-run or shared controller lifecycle.
- `src/app.py` is a broader continuous application with camera, keyboard override, EEG mapping, and photo support. Reuse its `process_eeg()`/mapper/action pattern as needed; do not copy its entire video loop into a simple timed movement skill.
- `scripts/jaw_takeoff.py` is a good mission template, but its `fly_once()` is deliberately local and only supports takeoff-hover-land. It is not a general movement API.

## Operational prerequisites and limits

- A Windows machine must run Unicorn Recorder/LSL and this program. The raw LSL stream must be enabled and named `UnicornRecorderRawDataLSLStream` unless `--stream` overrides it.
- The first eight stream columns must be the expected EEG channels; the code filters them by position.
- For physical flight, charge Tello above 20%, connect the laptop to `TELLO-XXXXXX`, and confirm the LSL stream before flight. The Tello hotspot has no internet.
- Use a clear area and a spotter. The controller’s `is_flying` is local state, so it cannot prove that a failed drone command changed real drone state.
- `jaw_takeoff.py` has no action mapping for a long-clench emergency; it only reacts to `JAW_SHORT`. In-flight emergency behavior is available in `src/app.py` through `CommandMapper` and `emergency_land()`.
- A live connection rejected for low battery returns from `main()` before `controller.shutdown()` runs. No flight is started, but future entry points should preserve a single cleanup path where practical.

## Classification for creating more skills

1. **Foundation to use for every drone skill:** `TelloController`, its RC tuple convention, `is_flying`, dry-run mode, bounded-duration commands, and `try`/`finally` shutdown.
2. **Foundation to use only when a skill is EEG-triggered:** `LslClient` -> preprocessing/features -> `ArtifactDetector` -> `Event`; calibrate thresholds before using a live person.
3. **Policy to use when several gestures/actions coexist:** `Event`/`Action`, `CommandMapper`, and `apply_action()` from `src/app.py`.
4. **Verification to retain:** dry-run first, the jaw-detector unit tests for detector changes, baseline recording/analysis for EEG threshold changes, then controlled hardware testing.
5. **Code to treat only as examples:** `Tello/Mover.py` and the local `fly_once()` mission. They show mechanics, but `TelloController` is the reusable abstraction.

