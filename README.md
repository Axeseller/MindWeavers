# Mind Weavers 2026

Control a DJI Tello with EEG artifacts from a Unicorn Hybrid Black headset.

One Windows laptop talks to both devices: Unicorn Recorder streams **raw** LSL, and this app maps jaw clenches and double blinks to Tello commands.

## Artifact map

| Artifact | Command |
|---|---|
| Short jaw clench (0.25–1.0 s) | Takeoff if grounded, else a short forward burst |
| Long jaw clench (> 1.2 s) | Land |
| Very long jaw clench (> 2.5 s) | Emergency land |
| Double blink (within 500 ms) | Take a photo |
| Single blink | Ignored |

Keyboard is always available as a safety override. See [docs/mapping.md](docs/mapping.md).

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

Full pipeline:

```bash
python src/app.py --dry-run
python src/app.py
```

`--dry-run` prints commands and never opens a Tello socket.

## Keyboard override

Focus the Tello camera window.

- `Q` takeoff
- `E` land
- `W` `S` `A` `D` forward / back / left / right
- `Y` `U` up / down
- `R` `T` yaw left / right
- `ESC` emergency exit (hover + land)

## Team

Axel, Ian, Chavez, Luisao, Hector.

- Unicorn / LSL: Recorder, stream name, `test_lsl.py`, baselines
- Tello SDK: `src/tello/controller.py`, safety, photo
- EEG mapping: `src/eeg/`, [docs/mapping.md](docs/mapping.md)
- Integration: `src/app.py`
- Demo / pitch: [docs/pitch.md](docs/pitch.md)
