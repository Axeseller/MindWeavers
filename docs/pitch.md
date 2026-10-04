# Pitch outline

Target length: 3–5 minutes plus a live demo.

## 1. Problem

Hands-busy or accessibility-constrained drone control still means a remote or a keyboard. EEG headsets exist in labs, but most BCI demos chase imagined movement and fail live.

## 2. Solution

Use artifacts the Unicorn already records loudly: jaw clench and double blink. Map three reliable events to takeoff, move, land, and photo. Keep a keyboard override so the demo can recover instantly.

## 3. Tech stack

- Unicorn Hybrid Black → Unicorn Recorder **raw** LSL (250 Hz)
- `pylsl` ring buffer → bandpass / notch → jaw RMS + frontal blink peaks
- Heuristic detector (no trained model on day 1)
- `djitellopy` controller copied from DroneOps Tello lessons (battery gate, hover, land-on-exit, camera)

## 4. Live demo

1. Headset on, stream visible.
2. Short clench → takeoff.
3. Short clench → forward burst.
4. Double blink → photo appears on disk / slide.
5. Long clench → land.

If EEG misfires, finish the same sequence from the keyboard.

## 5. Safety

Battery check before arming. Cooldown between flight commands. Idle hover is `(0, 0, 0, 0)`. Process exit always lands. Spotter in the room.

## 6. Closing

The demo is not “read the mind.” It is a working artifact BCI with a real aircraft and a photo you can hold up at the end.
