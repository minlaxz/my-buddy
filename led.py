from machine import Pin
from neopixel import NeoPixel


# Onboard WS2812. GPIO 38 is printed everywhere and is silently wrong for
# this board (writes raise nothing, pixel stays dark). Measured: 48.
LED_PIN = 48

# Percent of full scale when the caller gives none. Full scale is a 40 mA
# point source an arm's length from the owner's eyes; 5% reads across the room.
DEFAULT_BRIGHTNESS = 5


def parse_color(text):
    """(r, g, b) from '#rrggbb' / 'rrggbb', or None for off/invalid."""

    text = str(text).strip().lstrip("#")

    if len(text) != 6:
        return None

    try:
        return tuple(int(text[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return None


class Led:
    def __init__(self):
        self.pixel = NeoPixel(Pin(LED_PIN, Pin.OUT), 1)
        self.color = None  # "#rrggbb" as last set, or None when off
        self.off()

    def set(self, rgb, brightness=DEFAULT_BRIGHTNESS):
        scale = max(0, min(100, int(brightness))) / 100
        self.pixel[0] = tuple(int(c * scale) for c in rgb)
        self.pixel.write()
        self.color = "#{:02x}{:02x}{:02x}".format(*rgb)

    def off(self):
        self.pixel[0] = (0, 0, 0)
        self.pixel.write()
        self.color = None


led = Led()
