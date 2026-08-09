### Installation
```
import mip
mip.install("github:russhughes/st7789py_mpy/lib/st7789py.py")
mip.install("github:russhughes/st7789py_mpy/romfonts/vga1_8x8.py")
```

### Tests
```
import display
display.display.tft.fill(display.st7789.RED)
display.display.tft.fill(display.st7789.GREEN)
display.display.tft.fill(display.st7789.BLUE)
display.display.tft.fill(display.st7789.BLACK)
display.display.text("HELLO HERMES", 10, 10)
display.display.text("TFT ONLINE", 10, 30)
```
