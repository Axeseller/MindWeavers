# Inputs -> Tello

Seven inputs, the ones on the whiteboard. `fly.py` runs them all on one stream and an arbiter makes sure one
gesture becomes one input. The single-input scripts only print detections, for checking each one on its own.

| Input | Gesture | Action | Script |
|---|---|---|---|
| `jaw` | clench the jaw 0.5-2 s | takeoff / land | `jaw.py` (flies on its own) |
| `cerrar_ojos` | eyes closed 1.5 s | camera on / off | `cerrar_ojos.py` |
| `blink` | blink | photo (camera on) | `blink.py` |
| `brazos` | raise an arm, firmly | forward 1 s | `brazos.py` |
| `puno` | close a fist | back 1 s | `puno.py` |
| `cuello` | turn the head right | right 1 s | `cuello.py` |
| `angry` | frown | left 1 s | `angry.py` |

```bash
python scripts/artifacts/doctor.py                  # first: Python, libraries, Unicorn stream (--tello: drone too)
python scripts/artifacts/fly.py                     # all inputs, Tello dry-run: prints what it would do
python scripts/artifacts/fly.py --live              # real Tello
python scripts/artifacts/fly.py --inputs jaw,blink,cerrar_ojos   # a subset
python scripts/artifacts/fly.py --threshold cuello=20 --why      # tune one threshold; see what the arbiter drops
python scripts/artifacts/fly.py --replay <csv>      # a recording, no hardware
python scripts/artifacts/cuello.py                  # one detector alone
python scripts/artifacts/check_all.py <csv folder>  # every input on every recording, alone and through the arbiter
```

Where things live:
- **Cleaning** (channels, filter, window, statistic): `src/eeg/preprocess.py`, `ARTIFACT_CLEANING`.
- **Decision** (threshold, duration, direction, ceiling, refractory): `src/eeg/detectors.py`, `ARTIFACT_PARAMS`.
- **Arbiter** (priority, vetoes): `src/eeg/arbiter.py`.
- **Drone mapping**: `fly.py`, `PULSES` and `apply()`.

## How the arbiter keeps inputs apart
One gesture fires several detectors: a head turn is also a small body movement (`puno`) and some neck EMG
(`angry`); closing the eyes starts like a blink; a clench leaks into the blink band before the jaw RMS rises.
`InputArbiter` resolves that:
1. A firing is **pending for 0.5 s** instead of acting at once.
2. **Priority**: `jaw > cerrar_ojos > brazos > cuello > blink > angry > puno`. A higher one that fires replaces
   the pending one. If a higher one is still active (eyes still closed, arm still moving), the pending one
   waits: dropped if the higher one fires, emitted if it releases without firing. Blink sits above angry and
   puno because a wrong photo is harmless and a wrong pulse moves the drone.
3. **Vetoes**: `angry`, `puno` and `blink` are dropped when the head moved a lot meanwhile (gyroscope); `blink`
   also when the jaw EMG rose (a clench starting). `puno` and `angry` have a ceiling in their own feature too.
4. After an input is emitted, **1 s of silence**, including activations that began before it ended.

## Results on the 2026-10-04 recordings (`check_all.py`, table 2)
Nothing fires on the rest recording. Rows are what was done, columns what `fly.py` emitted.

| Done | jaw | cerrar_ojos | brazos | cuello | blink | angry | puno |
|---|---|---|---|---|---|---|---|
| jaw x18 | **15** | | | | | | |
| eyes closed x9 | | **8** | | | 2 | | |
| blink x18 | | | | | **15** | | |
| right arm x18 | | | **13** | | 1 | 1 | |
| left arm x18 | | 1 | **8** | 3 | | 1 | |
| head right x14 | | | | **13** | 1 | | |
| frown x14 | | | 1 | | 1 | **12** | |
| left fist x18 | | | | | 1 | | **10** |
| right fist x18 | | | | | 2 | | **11** |
| head left x14 (not an input) | 1 | | | 2 | | 1 | |

What this says:
- **Jaw, eyes, blink, head right, frown**: reliable, and nothing moves the drone by mistake.
- **Arms**: the right arm reads well; the left arm only 8/18 and 3 of them read as "right". Raise the arm firmly.
- **Fists**: 10-11 of 18. A fist barely reaches the headset; what is read is the small body movement. Any
  bigger movement is discarded on purpose, so stay still otherwise.
- **Turning the head left** is not an input and still fires something 4 times in 14. Only turn right.
- One session of one person. Expect lower numbers on another day; `--threshold` adjusts without code changes.
