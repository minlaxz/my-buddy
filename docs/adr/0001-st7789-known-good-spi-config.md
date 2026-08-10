# Keep the known-good ST7789 SPI configuration

The display init in `display.py` uses SPI mode 1 (polarity=1, phase=1) at 20 MHz with `color_order=BGR` on rotation 0. These values look wrong — ST7789 examples typically use mode 0 and RGB — but they are the empirically determined working configuration for this specific panel (1.54" 240x240 via st7789py). Do not "correct" them to the textbook values; that is how the display breaks.

## Consequences

- `Display()` is instantiated at module import time, and `main.py` imports it at boot. A bug in display init once put the ESP32 into a boot loop that could only be recovered by a full flash erase and re-flash. Treat any change to display init as high-risk: test it from the REPL before it lands in `main.py`'s import chain.
- The exact failure symptoms of the textbook config were not recorded; only the working values were kept.
