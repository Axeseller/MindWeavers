# Phase 4 — Calibration and integration verification

> The legacy `src/app.py` verification route has been retired. Verify the
> current multi-artifact pipeline with the replay, calibration, and dry-run
> commands in `scripts/artifacts/README.md`.

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
   python src/app.py --dry-run --replay <recording.csv>
   python src/app.py --dry-run     # needs the LSL stream
   ```

3. **EEG calibration (only if thresholds or gestures change)**

   ```bash
   python scripts/artifacts/calibrate.py
   python scripts/artifacts/check_all.py <folder with recordings>
   ```

   `calibrate.py` saves per-session thresholds that every script loads. Re-run the tests after changing `ARTIFACT_PARAMS`.

4. **Live smoke test (spotter required)**
   - Prerequisites: battery at least 20%, laptop on `TELLO-XXXXXX`, open area, Unicorn raw LSL verified with `scripts/test_lsl.py` before switching Wi-Fi (`docs/hardware.md`).
   - `python scripts/test_tello.py`
   - `python scripts/manual_mode.py --live`: takeoff, short press of each movement and yaw key, land.
   - `python src/app.py --simple`: short clench takes off, a second one lands; calibrate the session first.

## Acceptance criteria

- All unit tests pass.
- All dry-run entry points start and shut down cleanly.
- Live: each basic skill moves in the expected direction and the drone lands on `E`, `Esc`, `Ctrl+C` and short clench while flying.
