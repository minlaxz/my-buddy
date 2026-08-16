import time

from machine import Pin
from neopixel import NeoPixel


# Onboard WS2812 pixel. GPIO 38 looks plausible and is silently wrong: writing
# to it raises nothing, the pixel just stays dark. Measured on the board: 48.
BEACON_PIN = 48

# 5% of full scale. Full scale is a desk-blinding point source; 13/255 still
# reads across the room. ponytail: the only calibration knob — one LED is not
# as bright as another, tune here rather than in the colour table.
BEACON_BRIGHTNESS = 0.05

# Mirrors display.STATE_COLORS — same states, same hues, two surfaces.
# Sleeping is dark on purpose: the session ended, so no light is the honest
# reading rather than a colour meaning "gone".
STATE_RGB = {
    "working": (255, 255, 0),
    "idle": (0, 255, 0),
    "needs you": (255, 0, 0),
    "sleeping": (0, 0, 0),
}

# Matches the header's WHITE fallback for a state the Terminal does not know.
UNKNOWN_RGB = (255, 255, 255)

# Hue is identity, brightness is liveness: only states where something is
# happening or wanted breathe. States absent here are drawn solid.
BREATHE_MS = {
    "working": 2_000,
    "needs you": 600,
}

# The breathe never reaches black — a dark frame reads as "off", not "thinking".
BREATHE_FLOOR = 0.25


class Beacon:
    """The onboard RGB LED, showing Claude's Status as colour alone."""

    def __init__(self):
        self.np = NeoPixel(Pin(BEACON_PIN, Pin.OUT), 1)

        # The Beacon owns its state. Nothing can re-assert a state it retracted.
        self.state = None

        self.phase_start = 0

        # Last tuple actually written, so solid states cost no writes per tick.
        self.last = None

        # Dark until a Status arrives: at boot the Terminal knows nothing.
        self.off()

    def _write(self, rgb, level=255):
        b = BEACON_BRIGHTNESS * level / 255

        px = (
            int(rgb[0] * b),
            int(rgb[1] * b),
            int(rgb[2] * b),
        )

        if px == self.last:
            return

        self.last = px
        self.np[0] = px
        self.np.write()

    def _rgb(self):
        return STATE_RGB.get(str(self.state).lower(), UNKNOWN_RGB)

    def show(self, state):
        if state is None:
            self.off()
            return

        self.state = state

        # Restart the phase, so an attention state never opens on a dark frame.
        self.phase_start = time.ticks_ms()

        self._write(self._rgb())

    def off(self):
        self.state = None
        self._write((0, 0, 0))

    def tick(self, now):
        """Advance the breathe. No state, no light — a blanked Beacon stays blank."""

        if self.state is None:
            return

        cycle = BREATHE_MS.get(str(self.state).lower())

        if cycle is None:
            # Solid state: already drawn by show(), nothing to animate.
            return

        pos = time.ticks_diff(now, self.phase_start) % cycle

        half = cycle // 2

        # Triangle starting at the peak: the first frame of a new state is its
        # brightest, so "needs you" opens lit rather than mid-fade.
        if pos < half:
            level = 255 - (255 * pos // half)
        else:
            level = 255 * (pos - half) // (cycle - half)

        # Perceived brightness runs roughly as the square of drive, so a linear
        # ramp reads as a lingering top and a jump at the bottom.
        level = level * level // 255

        floor = int(255 * BREATHE_FLOOR)

        self._write(self._rgb(), floor + (255 - floor) * level // 255)


beacon = Beacon()


def demo():
    """On-device check: every state, the breathe, and the blank rule.

    mpremote connect <port> exec "import beacon; beacon.demo()"
    """

    for state in ("working", "needs you", "idle", "sleeping", "???"):
        print("[beacon]", state)

        beacon.show(state)

        deadline = time.ticks_add(time.ticks_ms(), 3_000)

        while time.ticks_diff(deadline, time.ticks_ms()) > 0:
            beacon.tick(time.ticks_ms())
            time.sleep_ms(20)

    # A breathing state must sweep the whole range, not sit at one level.
    beacon.show("working")

    seen = set()
    deadline = time.ticks_add(time.ticks_ms(), 2_100)

    while time.ticks_diff(deadline, time.ticks_ms()) > 0:
        beacon.tick(time.ticks_ms())
        seen.add(beacon.last)
        time.sleep_ms(20)

    assert (12, 12, 0) in seen, seen
    assert (3, 3, 0) in seen, seen

    # A blanked Beacon must stay blank however many ticks arrive.
    beacon.off()

    for _ in range(20):
        beacon.tick(time.ticks_ms())
        time.sleep_ms(20)

    assert beacon.last == (0, 0, 0), beacon.last

    # Scaling must never exceed the pixel's range.
    beacon.show("???")
    assert beacon.last == (12, 12, 12), beacon.last

    beacon.off()

    print("[beacon] demo ok")
