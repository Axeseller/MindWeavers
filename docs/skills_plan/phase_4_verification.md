# Phase 4 — Calibration and integration verification

## Goal

Prove the skills work from unit level to a supervised live flight, in that order. Stop at the first failing step.

## Steps

1. **Automated tests (no hardware)**

   ```bash
   python -m unittest discover -s tests
   ```

   Covers detector timing, skills/controller bursts, mapper policy and dispatch.

2. **Dry-run entry points**

   ```bash
   python scripts/test_tello.py --dry-run
   python scripts/manual_mode.py
   python src/app.py --dry-run --no-lsl
   python scripts/jaw_takeoff.py   # needs the LSL stream
   ```

3. **EEG calibration (only if thresholds or gestures change)**

   ```bash
   python scripts/record_baseline.py --label rest --seconds 30
   python scripts/record_baseline.py --label jaw --seconds 30
   python scripts/analyze_baselines.py --rest data/baselines/rest_*.csv --jaw data/baselines/jaw_*.csv
   ```

   Use the recommended value with `--threshold`. Re-run `tests/test_jaw_detector.py` after changing `DetectorConfig`.

4. **Live smoke test (spotter required)**
   - Prerequisites: battery at least 20%, laptop on `TELLO-XXXXXX`, open area, Unicorn raw LSL verified with `scripts/test_lsl.py` before switching Wi-Fi (`docs/hardware.md`).
   - `python scripts/test_tello.py`
   - `python scripts/manual_mode.py --live`: takeoff, short press of each movement and yaw key, land.
   - `python src/app.py`: short clench takes off, next short clench (after cooldown) lands; long clench lands.

## Acceptance criteria

- All unit tests pass.
- All dry-run entry points start and shut down cleanly.
- Live: each basic skill moves in the expected direction and the drone lands on `E`, `Esc`, `Ctrl+C` and short clench while flying.
