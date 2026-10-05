# Unicorn artifacts -> Tello

`src/app.py` is the program to run. It flies the Tello through `Tello/Mover.py` with six inputs, read from the
Unicorn LSL stream and kept apart by an arbiter (one gesture = one command).

| Gesture | Mover.py key | Action |
|---|---|---|
| jaw clench (1st) | Q | takeoff |
| turn the head (either side) | W | forward 1 s |
| blink | S | back 1 s |
| smile (happy) | D | right 1 s |
| frown (angry) | A | left 1 s |
| eyes closed ~1.5 s | - | turn 90° right (`tello.rotate_clockwise(90)`), once per closure |
| jaw clench (2nd) | E | land |

```bash
python scripts/artifacts/doctor.py      # 1. Python, libraries, Unicorn stream (--tello: drone too)
python scripts/artifacts/calibrate.py --inputs jaw,cerrar_ojos,cuello,blink,angry,happy   # 2. ~5 min, per person
python src/app.py --dry-run             # 3. no drone: prints what it would send
python src/app.py                       # 4. real Tello (connect to its Wi-Fi first); Ctrl+C lands
```

Options for `src/app.py`:
- `--lados`: five inputs, without the eyes-closed turn (`vuelo5.py`).
- `--simple`: only jaw, neck and blink (`vuelo.py`).
- `--why`: print the firings the arbiter dropped, and why.
- `--threshold cuello=15`: try a threshold without recalibrating.
- `--no-calibration`: ignore the saved calibration.
- `--loose-faces`: drop the smile/frown pattern checks.
- `--replay <csv>`: run on a recording (with `--dry-run`).

Keep the eyes open while flying: a closure turns the drone, and without seeing it for 1.5 s.

## Files

| File | What it is |
|---|---|
| `vuelo.py` | The flight loop: headset -> arbiter -> Mover.py keys -> Tello. Three inputs by default. |
| `vuelo5.py`, `vuelo6.py` | Same loop with five / six inputs (`src/app.py` runs `vuelo6.py`). |
| `calibrate.py` | Guided calibration: rest + each input 6 times, fits thresholds and face patterns to the person. |
| `check_all.py` | Every input on every recording, alone and through the arbiter. |
| `doctor.py` | Checks the setup before flying. |
| `jaw.py`, `blink.py`, `cerrar_ojos.py`, `cuello.py`, `angry.py`, `happy.py`, `puno.py` | One detector alone, printing detections (`jaw.py` also takes off and lands). |
| `_live.py`, `_paths.py` | Shared loop for the single-input scripts, CSV replay, import paths. |

Where the parameters live:
- **Cleaning** (channels, filter, window, statistic): `src/eeg/preprocess.py`, `ARTIFACT_CLEANING`; the arbiter's
  extra measurements in `GAUGE_CLEANING`.
- **Decision** (threshold, duration, direction, ceiling, refractory): `src/eeg/detectors.py`, `ARTIFACT_PARAMS`.
- **Arbiter** (priority, gates, face limits): `src/eeg/arbiter.py`.
- **Calibration**: `src/eeg/calibration.py`, saved to `data/calibration/thresholds.json` (not committed; every
  script loads it when it exists).

## How the arbiter keeps inputs apart
One gesture fires several detectors: a head turn is also a small body movement and neck EMG; closing the eyes
starts like a blink and squeezes the face; a blink leaks into the smile band; a clench leaks into the blink band.
`InputArbiter`:
1. A firing is a **candidate for 0.5 s** instead of acting at once.
2. **Priority** `jaw > cerrar_ojos > cuello > blink > angry > happy > puno`: the highest candidate that passes its
   gate wins. While a higher detector is still active (eyes still closed, head still turning) the decision waits.
3. **Gates**, checked on everything seen from the onset to the decision:

   | Input | Must look like |
   |---|---|
   | cuello | mostly yaw: pitch <= 0.6 x yaw (an arm raise tips the head instead) |
   | blink | head still, no clench starting; eyes reopened if `cerrar_ojos` is not enabled |
   | angry | the frown's frontal/occipital EMG pattern, eyes open, head moved <= 12 |
   | happy | the smile's pattern, eyes open, no blink, no clench, head still |
   | puno | head moved <= 8 |

   The frown/smile pattern differs between people; `calibrate.py` fits it to the pilot.
4. After a command, **1 s of silence**, including activations that started before it ended.

## Results on the 2026-10-04 recordings (`check_all.py --only jaw,cerrar_ojos,cuello,blink,angry,happy`)
Nothing fires at rest. Rows are what was done, columns what `src/app.py` emitted.

| Done | jaw | cerrar_ojos | cuello | blink | angry | happy |
|---|---|---|---|---|---|---|
| jaw x18 | **15** | | | | | |
| eyes closed x9 | | **8** | | 2 | | |
| blink x18 | | | | **15** | | |
| head right x14 | | | **15** | 1 | | |
| head left x14 | 1 | | **17** | | | |
| frown x14 | | | | 1 | **12** | 1 |
| smile x14 | | | | | | **13** |

- The neck counts both sides; now and then the return swing adds an extra forward.
- Fists (`puno.py`) are not in the flight: the headset barely sees the hand.
- One session of one person; on another person or day, run `calibrate.py` first.
