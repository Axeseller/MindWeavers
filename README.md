# Mind Weavers 2026

Control a DJI Tello with EEG artifacts from a Unicorn Hybrid Black headset.

One Windows laptop talks to both devices: Unicorn Recorder streams **raw** LSL, and
`src/app.py` is the main program: jaw takes off and lands, turning the head goes forward, a blink goes back,
a smile goes right, a frown goes left and closing the eyes turns 90° right.

## Artifact map

| Input | Command (`src/app.py`) |
|---|---|
| Jaw clench | Take off when grounded; land when flying |
| Head turn (either side) | Forward 1 s |
| Blink | Back 1 s |
| Smile | Right 1 s |
| Frown | Left 1 s |
| Eyes closed ~1.5 s | Turn 90° right |

See [the artifact runner guide](scripts/artifacts/README.md) for calibration,
recorded results, and the known limitations of each input.

## Setup (Windows flight laptop)

Install packages **before** joining the Tello Wi-Fi hotspot (that network has no internet):

```bash
cd ~/Dev/MindWeavers
python -m pip install -r requirements.txt
```

1. Pair the Unicorn with the **provided Bluetooth dongle** (not the laptop radio).
2. Open Unicorn Recorder and enable **raw** LSL. Default stream name: `UnicornRecorderRawDataLSLStream`.
3. Do **not** enable OSCAR. OSCAR removes blinks and motion, which this project detects.
4. Confirm LSL, then connect the same laptop to `TELLO-XXXXXX`.

Hardware notes: [docs/hardware.md](docs/hardware.md).

## Run

Print live LSL samples (no drone):

```bash
python scripts/test_lsl.py
```

Tello smoke test (battery, takeoff, photo, land):

```bash
python scripts/test_tello.py
python scripts/test_tello.py --dry-run
```

Record labeled baselines for threshold tuning:

```bash
python scripts/record_baseline.py --label jaw --seconds 30
python scripts/record_baseline.py --label blink --seconds 30
```

Manual flight (jaw clench = takeoff/land switch, keyboard = movement skills). Dry-run by default:

```bash
python scripts/manual_mode.py
python scripts/manual_mode.py --no-eeg
python scripts/manual_mode.py --live
```

Main program (flies the real Tello by default; `--dry-run` prints instead):

```bash
python scripts/artifacts/doctor.py
python scripts/artifacts/calibrate.py --inputs jaw,cerrar_ojos,cuello,blink,angry,happy
python src/app.py --dry-run
python src/app.py
python src/app.py --lados     # without the eyes-closed turn
python src/app.py --simple    # only jaw, neck and blink
```

`src/app.py` runs `scripts/artifacts/vuelo6.py` through `Tello/Mover.py`: jaw clench (1st) takes off, turning the
head goes forward 1 s, a blink goes back 1 s, a smile goes right, a frown goes left, closing the eyes turns 90°
right, jaw clench (2nd) lands. Use replay and dry-run before flying.

Tests (no hardware):

```bash
python -m unittest discover -s tests
```

## Manual flight

Use Manual Mode to validate drone movement and retain a keyboard-only control
path. Focus the Tello camera window.

- `Space` takeoff/land switch
- `Q` takeoff, `E` land
- `W` `S` `A` `D` forward / back / left / right (hold to keep moving)
- `Y` `U` up / down
- `R` `T` yaw left / right
- `ESC` exit (waits for a running takeoff/land, then lands)

While takeoff or landing runs, every other input is ignored. `src/app.py`
uses Ctrl+C to land and exit; do not rely on it as a replacement for a manual
flight safety procedure.

## Team

Axel, Ian, Chavez, Luisao, Hector.

- Unicorn / LSL: Recorder, stream name, `test_lsl.py`, baselines
- Tello SDK: `src/tello/controller.py`, safety, photo
- EEG mapping: `src/eeg/`, [docs/mapping.md](docs/mapping.md)
- Integration: `src/app.py` (runs `scripts/artifacts/vuelo6.py`)
- Demo / pitch: [docs/pitch.md](docs/pitch.md)
