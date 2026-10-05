While the tello drone can right now take off and land using: jaw_takeoff.py --live

Its required to create "skills" that allow the tello drone to do more actions, this include:

### MOVEMENT

-Forward
-Back
-Right
-Left
-Up
-Down

### STATE

-Takeoff/Land (Actions depends if the drone is already in the air or grounded. Could reuse is_flying variable)

### Rotation

-Clockwise
-CounterClock

This collection of skills can be categorized as the "Basic" movement skills.

Shortcuts: We can use Mover.py and jaw_takeoff.py as blueprints to create modular functions for each skill, then call them in a "Manual_Mode" file which would act as a free controller for the user.

About jaw clench: Jaw clench "short" should conntrol both takeoff and Land in a single input, depending of is_flying variable. (edit current events so that it matches the current use of jaw clench short.)

Goal: To create the structure and leave everything ready so that the input data can be inserted into the arguments and tested.

Note: This file is only meant to express the idea and plan to create more skills for the drone and is not a canonical source of truth.
