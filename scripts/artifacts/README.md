# Inputs -> Tello

## Simple flight: `vuelo.py`
Three inputs, connects to the real Tello by default. Each gesture becomes the key `Tello/Mover.py` would get
(Q, W, S, E) and is executed the same way Mover.py does it:

| Gesture | Action |
|---|---|
| jaw clench (1st) | Q: takeoff |
| turn the head (either side) | W: forward 1 s |
| blink | S: back 1 s |
| jaw clench (2nd) | E: land |

```bash
python scripts/artifacts/calibrate.py --inputs jaw,cuello,blink   # once per person (~3 min)
python scripts/artifacts/vuelo.py --dry-run                       # test without the drone
python scripts/artifacts/vuelo.py                                 # real flight (Tello Wi-Fi first); Ctrl+C lands
```
Keep the eyes open while flying: without the cerrar_ojos input, a closure is filtered by its alpha, but about 1 in
4 still reads as a blink (back). The neck turn counts to either side; now and then the return swing adds an extra
forward.

### With left and right: `vuelo5.py`
A copy of the same flight plus two inputs (`vuelo.py` stays as it is):

| Gesture | Action |
|---|---|
| smile (happy) | D: right 1 s |
| frown (angry) | A: left 1 s |

```bash
python scripts/artifacts/calibrate.py --inputs jaw,cuello,blink,angry,happy
python src/app.py --lados --dry-run       # or: python scripts/artifacts/vuelo5.py --dry-run
python src/app.py --lados
```
On the recordings happy reads 13 of 14 and angry 12 of 14, and they never read as each other.

## Full set: `fly.py`

Seven inputs, the ones on the whiteboard. `fly.py` runs them all on one stream and an arbiter makes sure one
gesture becomes one input. The single-input scripts only print detections, for checking each one on its own.

| Input | Gesture | Action | Script |
|---|---|---|---|
| `jaw` | clench the jaw 0.5-2 s | takeoff / land | `jaw.py` (flies on its own) |
| `cerrar_ojos` | eyes closed 1.5 s | camera on / off | `cerrar_ojos.py` |
| `blink` | blink | photo (camera on) | `blink.py` |
| `happy` | smile big | forward 1 s | `happy.py` |
| `puno` | close a fist | back 1 s | `puno.py` |
| `cuello` | turn the head (either side) | right 1 s | `cuello.py` |
| `angry` | frown | left 1 s | `angry.py` |

```bash
python scripts/artifacts/doctor.py                  # 1. Python, libraries, Unicorn stream (--tello: drone too)
python scripts/artifacts/calibrate.py               # 2. ~5 min guided calibration, once per person and session
python scripts/artifacts/fly.py                     # 3. all inputs, Tello dry-run: prints what it would do
python scripts/artifacts/fly.py --live              #    real Tello
python scripts/artifacts/fly.py --inputs jaw,blink,cerrar_ojos   # a subset
python scripts/artifacts/fly.py --threshold cuello=20 --why      # try a threshold; see what the arbiter drops
python scripts/artifacts/calibrate.py --inputs puno # recalibrate one input (the others keep theirs)
python scripts/artifacts/fly.py --replay <csv>      # a recording, no hardware
python scripts/artifacts/check_all.py <csv folder>  # every input on every recording, alone and through the arbiter
```

Where things live:
- **Cleaning** (channels, filter, window, statistic): `src/eeg/preprocess.py`, `ARTIFACT_CLEANING`; the arbiter's
  extra measurements in `GAUGE_CLEANING`.
- **Decision** (threshold, duration, direction, ceiling, refractory): `src/eeg/detectors.py`, `ARTIFACT_PARAMS`.
- **Arbiter** (priority, gates): `src/eeg/arbiter.py`.
- **Calibration** (per-session thresholds): `src/eeg/calibration.py`, saved to `data/calibration/thresholds.json`
  (not committed; every script loads it when it exists).
- **Drone mapping**: `fly.py`, `PULSES` and `apply()`.

## Calibration
Thresholds tested on one person's recordings rarely fit someone else. `calibrate.py` asks for 20 s of rest and
each input 6 times (`>>> NOW` prompts, with a beep), saves the raw session under `data/calibration/`, and picks
each threshold by replaying the whole session through the arbiter: catch every repetition, fire on nothing
else. It ends with a table of how `fly.py` reads your session; any number off the diagonal is a confusion that
remains. `--analyze <session folder>` recalibrates a saved session without the headset.

## How the arbiter keeps inputs apart
One gesture fires several detectors: a head turn is also a small body movement (`puno`) and neck EMG (`angry`);
closing the eyes starts like a blink and squeezes the face (`angry`); a blink leaks into the smile band (`happy`);
a clench leaks into the blink band.
`InputArbiter`:
1. A firing is a **candidate for 0.5 s** instead of acting at once.
2. **Priority** `jaw > cerrar_ojos > cuello > blink > angry > happy > puno`: the highest candidate that passes its
   gate wins, the rest are dropped. While a higher detector is still active (eyes still closed, head still
   turning) the decision waits. Blink sits above angry, happy and puno: a wrong photo is harmless, a wrong pulse
   moves the drone.
3. **Gates**, checked on everything seen from the onset to the decision:

   | Input | Must look like | Measured on the recordings |
   |---|---|---|
   | cuello | mostly yaw: pitch <= 0.6 x yaw | neck <= 0.27, arm raise >= 0.73 |
   | angry | frontal/occipital EMG <= 0.85 at its peak; eyes open (alpha <= 5); head moved <= 12 | frown 0.47-0.88, alpha 1.7-3.4; eyes closing: alpha 8-14 |
   | happy | frontal/occipital EMG >= 0.9; eyes open; no blink (eye deflection <= 22); no clench; head still | smile 0.90-1.30, deflection 13-20; blink 25-72 |
   | puno | head moved <= 8 | |
   | blink | head moved <= 8; jaw EMG <= 15 (not a clench starting) | |

4. After a command, **1 s of silence**, including activations that started before it ended.

## Results on the 2026-10-04 recordings (`check_all.py`, table 2)
Nothing fires at rest. Rows are what was done, columns what `fly.py` emitted.

| Done | jaw | cerrar_ojos | cuello | blink | angry | happy | puno |
|---|---|---|---|---|---|---|---|
| jaw x18 | **15** | | | | | | |
| eyes closed x9 | | **8** | | 2 | | | |
| blink x18 | | | | **15** | | | |
| head right x14 | | | **14** | 1 | | | |
| frown x14 | | | | 1 | **12** | | 1 |
| smile x14 | | | | | | **13** | |
| left fist x18 | | | 1 | 1 | | | **5** |
| right fist x18 | | | | 1 | | 1 | **9** |
| arm raises x36 (not inputs) | | | | 1 | 2 | | 1 |

What is left:
- **Eyes closed -> 2 photos**: probably real blinks between the closures (people blink when they reopen).
- **Fists** are the weakest input. The headset cannot see the hand, only the small body movement, so any small
  head movement can fire it. The default threshold is raised so it stays quiet; `calibrate.py` lowers it as far
  as your rest allows (on these recordings: 12 and 13 of 18). Stay still when not using it, or leave it out
  with `--inputs`.
- One session of one person; on another person or day, run `calibrate.py` first.
