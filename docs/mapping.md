# Artifact to command mapping

Do not change this table during a flight session. Tune detector thresholds, not the meaning of each event.

## Events

| Event | How it is detected | Tello action |
|---|---|---|
| `JAW_SHORT` | Jaw EMG stays above threshold for 0.25–1.0 s, then drops | Takeoff if grounded; otherwise a ~0.6 s forward burst |
| `JAW_LONG` | Jaw EMG stays above threshold for more than 1.2 s | Land |
| `JAW_EMERGENCY` | Jaw EMG stays above threshold for more than 2.5 s | Emergency land |
| `DOUBLE_BLINK` | Two frontal blink peaks within 500 ms | Save a still from the Tello camera |
| Single blink | One isolated frontal peak | Ignored — people blink constantly |

Flight commands share a **1.0 s cooldown** so one clench cannot fire a burst of takeoffs.

## Why these artifacts

Motor imagery is too noisy for a one-day demo. Jaw clench is loud EMG across many EEG channels. Double blink is a large, slow frontal peak. Both are visible by eye on a raw Unicorn stream.

## Feature split

- **Jaw:** RMS of 15–40 Hz energy across EEG channels 1–8. Blinks are slower, so they stay out of this band.
- **Blink:** mean absolute amplitude of 1–10 Hz on frontal channels (EEG 1–2, indices 0 and 1).

## Thresholds

Defaults live in `src/eeg/detectors.py` (`DetectorConfig`). After `scripts/record_baseline.py` sessions:

1. Record ~20 jaw clenches and ~20 double blinks.
2. Plot RMS and frontal amplitude.
3. Set `jaw_rms_threshold` just above rest.
4. Set `blink_peak_threshold` just above a normal single blink's rest floor, high enough that only clear blinks trigger.

Use hysteresis (release at 60% of the enter threshold) so the jaw state does not flicker.

## Keyboard override

Keyboard commands skip the EEG mapper and go straight to the controller. They are the safety net if a detector misfires.
