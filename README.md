# Mind Weavers 2026

Control a DJI Tello with EEG artifacts from a Unicorn Hybrid Black headset.

One Windows laptop talks to both devices: Unicorn Recorder streams **raw** LSL, and this app maps jaw clenches and double blinks to Tello commands.

## Artifact map

| Artifact | Command |
|---|---|
| Short jaw clench (~0.5–1 s) | Switch: takeoff if grounded, land if flying |
| Long jaw clench (~1.5 s or more) | Land |
| Very long jaw clench (~10 s) | Land (motors are never cut) |
| Double blink (within 500 ms) | Take a photo (`app.py`) |
| Single blink | Ignored |

Movement skills (forward, back, left, right, up, down, yaw) have no EEG gesture yet; the keyboard drives them. Keyboard is always available as a safety override. See [docs/mapping.md](docs/mapping.md) and [docs/skills_plan/phase_5_skill_runner.md](docs/skills_plan/phase_5_skill_runner.md).

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

Full pipeline (adds the double-blink photo):

```bash
python src/app.py --dry-run
python src/app.py
```

`--dry-run` prints commands and never opens a Tello socket. Both accept `--threshold` (jaw RMS, default 40).

Tests (no hardware):

```bash
python -m unittest discover -s tests
```

## Keyboard override

Focus the Tello camera window.

- `Space` takeoff/land switch
- `Q` takeoff, `E` land
- `W` `S` `A` `D` forward / back / left / right (hold to keep moving)
- `Y` `U` up / down
- `R` `T` yaw left / right
- `ESC` exit (waits for a running takeoff/land, then lands)

While takeoff or landing runs, every other input is ignored.

## Team

Axel, Ian, Chavez, Luisao, Hector.

- Unicorn / LSL: Recorder, stream name, `test_lsl.py`, baselines
- Tello SDK: `src/tello/controller.py`, safety, photo
- EEG mapping: `src/eeg/`, [docs/mapping.md](docs/mapping.md)
- Integration: `src/app.py`
- Demo / pitch: [docs/pitch.md](docs/pitch.md)
