# One script per artifact

Each file reads the Unicorn LSL stream, cleans the signal its own way and prints `>>> DETECTED: <name>` when its artifact happens. Only `jaw.py` moves the drone (take off, hover, land). Once we know which ones read well on the headset, we put a drone command in each `on_detect()`.

```bash
python scripts/artifacts/blink.py                  # headset LSL, Tello dry-run
python scripts/artifacts/blink.py --live           # headset LSL, real Tello
python scripts/artifacts/blink.py --threshold 40   # try another threshold
python scripts/artifacts/blink.py --replay <csv>   # a recorded CSV, no hardware
python scripts/artifacts/check_all.py <csv folder> # every detector on every recording
```

## Camera mode
```bash
python scripts/artifacts/camera.py        # close eyes 1.5 s: camera on / off. Blink: photo (only while on)
```
`camera.py` runs `cerrar_ojos` and `blink` together, because closing or opening the eyes also looks like a blink:
- **Blinks wait 0.6 s before they count.** If the eyes stay closed in that time, it was a close, not a blink.
- **Blinks are ignored for 1 s after the eyes open.**

On the recordings this filtering cut false photos:
- **Closing the eyes:** from 29 to 1.
- **Jaw clench:** from 19 to 1.

It also costs some real blinks: it now takes 14 of the 18. Photos go to `data/recordings/`. Natural blinks also take photos while the camera is on.

Where things live:
- **Cleaning** (channels, filter, CAR, window, statistic): `src/eeg/preprocess.py`, `ARTIFACT_CLEANING`.
- **Decision** (threshold, duration, direction, refractory): `src/eeg/detectors.py`, `ARTIFACT_PARAMS`.
- **Live loop:** `_live.py`, the same steps as `scripts/jaw_takeoff.py`.

## Results on the 2026-10-04 recordings (`check_all.py`)

None of the detectors fires on the rest recording.

| Script | Signal | Own recording | Also fires on |
|---|---|---|---|
| `jaw` | EMG 15-40 Hz, 0.5-2 s | 15 / 18 | - |
| `blink` | Fz 0.5-8 Hz, signed | 18 / 18 | jaw, eyes closing, eye movement with eyes closed |
| `cerrar_ojos` | occipital alpha held 1.5 s | 9 / 9 | - |
| `cuello_izq` | gyro yaw + | 14 / 14 | 2 from brazo der |
| `cuello_der` | gyro yaw − | 14 / 14 | brazo izq (8) |
| `giro_imag_izq` | gyro pitch − | 14 / 14 | real neck and arm movements |
| `giro_imag_der` | gyro pitch + | 11 / 14 | brazo der (9), cuello izq (5) |
| `enojado` | EMG 15-40 Hz | 14 / 14 | any muscle activity (jaw, neck, arms) |
| `happy` | EMG 30-100 Hz after CAR | 13 / 14 | blinks, neck, arms |
| `brazo_izq` | gyro yaw − | 14 / 18 | cuello der (15) |
| `puno_izq` / `puno_der` | gyro magnitude | 11 / 18, 14 / 18 | each other, and almost everything else |

Raising the right arm no longer has a script: either fist takes its command (up).

How to read the table:
- **Head and arm movements are read by the gyroscope.** The head turns with them. This includes the imagined head turns: the person still moved slightly, and no EEG feature separated those recordings from rest.
- **Left/right pairs** fire only when the first movement goes their way, and they then ignore the return swing. Even so, a real neck turn and raising the arm on the other side look the same: both turn the head the same way.
- **The fists cannot be told apart.** The scalp barely sees the hand.
- These numbers come from one session of one person, replayed through the same code as the live loop. Expect lower numbers on another day.
