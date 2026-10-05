# Legacy event-to-command mapping

> Retired as the runtime integration path. The supported artifact mapping,
> calibration, and conflict-resolution policy live in
> [`scripts/artifacts/fly.py`](../scripts/artifacts/fly.py) and
> [`scripts/artifacts/README.md`](../scripts/artifacts/README.md).
> `src/app.py` is now a compatibility wrapper only.

Do not change this table during a flight session. Tune detector thresholds, not the meaning of each event.

## Events

Timings below are from `jaw_takeoff_config()`, the calibrated detector used by `manual_mode.py`, `app.py` and `jaw_takeoff.py`. They are measured on the 1 s jaw-RMS feature, so they run longer than the clench itself.

| Event | How it is detected | Tello action |
|---|---|---|
| `JAW_SHORT` | Jaw RMS stays above threshold for 0.5–2.0 s, then drops (a ~0.5–1 s clench) | Takeoff if grounded; land if flying (switch) |
| `JAW_LONG` | Jaw RMS stays above threshold for 2.0 s or more, then drops | Land |
| `JAW_EMERGENCY` | Jaw RMS stays above threshold for 10 s | Land (normal landing, motors are never cut) |
| `DOUBLE_BLINK` | Two frontal blink peaks within 500 ms | Save a still from the Tello camera (`app.py` only) |
| Single blink | One isolated frontal peak | Ignored — people blink constantly |
| `ROTATE_CW` | Not detected yet — gesture to be chosen and calibrated | Yaw clockwise burst (only while flying) |
| `ROTATE_CCW` | Not detected yet — gesture to be chosen and calibrated | Yaw counter-clockwise burst (only while flying) |

Flight commands share a **1.0 s cooldown** so one clench cannot take off and immediately land. Events fire on clench release.

Takeoff and land are **process** skills: while one runs, every other input is ignored. Movement actions (`FORWARD`, `BACK`, `LEFT`, `RIGHT`, `UP`, `DOWN`, `YAW_CW`, `YAW_CCW`) are **continuous** skills routed by `ACTION_SKILLS` to `SkillRunner.request()`. No EEG event is bound to them yet. To bind a gesture, add an `Event` and one branch in `CommandMapper.map()`. See [skills_plan/phase_5_skill_runner.md](skills_plan/phase_5_skill_runner.md).

## Why these artifacts

Motor imagery is too noisy for a one-day demo. Jaw clench is loud EMG across many EEG channels. Double blink is a large, slow frontal peak. Both are visible by eye on a raw Unicorn stream.

## Feature split

- **Jaw:** RMS of 15–40 Hz energy across EEG channels 1–8. Blinks are slower, so they stay out of this band.
- **Blink:** mean absolute amplitude of 1–10 Hz on frontal channels (EEG 1–2, indices 0 and 1).

## Thresholds

Defaults live in `src/eeg/detectors.py` (`DetectorConfig`); the flight scripts use `jaw_takeoff_config(threshold)` and accept `--threshold`. After `scripts/record_baseline.py` sessions:

1. Record ~20 jaw clenches and ~20 double blinks.
2. Plot RMS and frontal amplitude.
3. Set `jaw_rms_threshold` just above rest.
4. Set `blink_peak_threshold` just above a normal single blink's rest floor, high enough that only clear blinks trigger.

Use hysteresis (release at 60% of the enter threshold) so the jaw state does not flicker.

## Keyboard override

Keyboard commands skip the EEG mapper (`key_to_action()`) and go through the same `SkillRunner` as EEG events. They are the safety net if a detector misfires. `Space` is the takeoff/land switch; holding a movement key keeps moving.
