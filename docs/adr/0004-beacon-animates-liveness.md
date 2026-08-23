---
status: deprecated
---

> Deprecated 2026-08-23: ntfy, Status and the Beacon were removed from the Terminal (test-phase features). Kept for the record.

# The Beacon animates liveness, not identity

Supersedes the "solid colour, v1" line of ADR-0003. The Beacon now breathes on `working` and pulses on `needs you`; `idle` and `sleeping` stay as they were.

**Brightness moves, hue never does.** The obvious use of an RGB LED is more colours — drift yellow through orange while working, cycle a rainbow. It was rejected. Colour is how a state is *named* on this device: yellow means `working` in the header and on the Beacon, and a yellow that wanders is a name that wanders. Brightness carries the second axis instead, so a glance answers "which state" by hue and "is it live" by movement, with neither reading interfering with the other. Rainbow remains available for some future state that has no colour of its own.

**Only states that mean something-is-happening animate.** `working` breathes over 2 s, `needs you` over 600 ms. `idle` is solid and `sleeping` is dark. Animating everything would spend the whole attention budget on a light that means "nothing to do" — and a desk object that never stops moving is one you stop seeing.

**The ramp is a triangle, then squared.** Perceived brightness runs roughly as the square of drive current, so a linear ramp reads as lingering at the top with a jump at the bottom. Squaring the triangle before mapping it into the floor..peak range costs one multiply and no `math` import, and is the difference between "breathing" and "flickering between two levels".

**It never reaches black.** The floor is 25% of the state's peak. A breathe that touches zero is indistinguishable from the Beacon being off, which is a meaning already taken — off means the Terminal has no Status it can justify.

**The phase restarts on every state change, at the peak.** A free-running counter can land a new `needs you` at the dark end of its cycle, so the first statement of "I need you" would be dimmer than the state it replaced. Attention signals begin lit.

**The Beacon owns its state; `tick()` renders what it holds.** `off()` clears the state, so a `tick()` after the stale-link blank of ADR-0003 draws nothing. Had `main.py` passed the state into each tick instead, the animation would immediately resurrect a colour the blank had just retracted — the dead-link rule would have quietly stopped working the moment animation landed.

**`tick()` is called every loop pass, not on the existing 100 ms animation timer.** That timer sits after the message popup's `continue`, so a 5 s Notification would freeze the breathe — including the popup that accompanies `needs you`, which is exactly when the pulse matters. `tick()` writes the pixel only when the computed level changes, so the extra passes cost arithmetic and no bitbang.

## Consequences

- ADR-0003's claim that the Beacon "costs the main loop nothing between Status messages" now holds only for `idle` and `sleeping`. A breathing state computes a level every pass and writes on change — still far below the SPI traffic the display generates.
- Changing a breathe rate is a number in `BREATHE_MS`; adding a state to it turns that state from solid to breathing with no other edit. Removing one is equally cheap, which is the intended way to walk this back if the movement turns out to be noise.
- The 600 ms pulse at a 20 ms tick gets ~30 steps, so it is smooth. It was designed against the 100 ms timer, where it would have had 6 and looked steppy; the per-pass call fixed that as a side effect of the popup problem.

