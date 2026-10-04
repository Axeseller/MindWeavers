# Hardware setup

## Machines

The official Unicorn Suite is Windows-only. Run Unicorn Recorder and this Python app on **one Windows laptop** so that laptop can see both the LSL stream and the Tello Wi-Fi.

Fedora (or any other machine) can edit code. Copy the repo to the Windows laptop before flight tests.

## Unicorn Hybrid Black

1. Plug in the **Unicorn Bluetooth dongle**. Do not pair with the laptop's built-in radio.
2. Install [Unicorn Suite Hybrid Black](https://github.com/unicorn-bi/Unicorn-Suite-Hybrid-Black).
3. Open **Unicorn Recorder** (Apps) or **Unicorn LSL** (DevTools).
4. Enable **Raw Data LSL Output**.
5. Stream name must match the app default: `UnicornRecorderRawDataLSLStream`.
6. Leave **OSCAR off**. OSCAR is built to remove blinks and motion artifacts.
7. Sampling rate is 250 Hz. A full scan is 17 channels:

| Index | Channel |
|---|---|
| 0–7 | EEG 1–8 |
| 8–10 | Accelerometer X Y Z |
| 11–13 | Gyroscope X Y Z |
| 14 | Battery |
| 15 | Counter |
| 16 | Validation |

Confirm with:

```bash
python scripts/test_lsl.py
```

You should see samples printing. If resolve times out, the stream name or Recorder output is wrong.

## DJI Tello

1. Charge above 20%. The controller refuses takeoff below that, same as the DroneOps `Inicio.py` lesson.
2. Power the drone and join `TELLO-XXXXXX` from the Windows laptop.
3. That hotspot has **no internet**. Install `requirements.txt` first.
4. Confirm with:

```bash
python scripts/test_tello.py --dry-run
python scripts/test_tello.py
```

5. Fly in an open area with a spotter. Keep a finger on `E` / `ESC`.

## Network conflict

The laptop cannot stay on campus Wi-Fi and Tello Wi-Fi at the same time. Sequence:

1. Install Python packages on internet Wi-Fi.
2. Start Unicorn Recorder and verify LSL (Unicorn uses Bluetooth, not Wi-Fi).
3. Switch the laptop Wi-Fi to Tello.
4. Run `src/app.py`.
