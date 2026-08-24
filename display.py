from machine import Pin, SPI
import st7789py as st7789
import vga1_8x16 as font


# Buddy TFT pin assignment
TFT_MOSI = 11
TFT_SCLK = 12
TFT_CS = 8
TFT_DC = 9
TFT_RST = 10

TFT_WIDTH = 240
TFT_HEIGHT = 240

# 8x16 font: 30 columns, rows 16px tall.
LINE_1_Y = 36
LINE_2_Y = 56

# Message area: below the Wi-Fi lines, above the Heartbeat.
MESSAGE_Y = 84
MESSAGE_ROWS = 7
MESSAGE_COLS = 29

# Relay state row: bottom-left, same baseline as the Heartbeat dots.
RELAY_Y = 208


def wrap(text, width):
    """Split text into lines of at most `width` chars, keeping existing breaks."""

    lines = []

    for paragraph in text.split("\n"):
        while len(paragraph) > width:
            cut = paragraph.rfind(" ", 0, width + 1)

            if cut <= 0:
                cut = width

            lines.append(paragraph[:cut])
            paragraph = paragraph[cut:].lstrip()

        lines.append(paragraph)

    return lines


def link_lines(link):
    """The two Page lines for a Wi-Fi Link, or for no link at all.

    link: (ssid, ip, rssi) or None. rssi may be None.
    Returns ((label, value, value_colour), line2_or_None).
    """

    if link is None:
        return ("SSID: ", "Disconnected", st7789.RED), None

    ssid, ip, rssi = link

    rssi_text = "--" if rssi is None else str(rssi)

    # ponytail: no "RSSI:" label — "dBm" already says it, and with the label
    # a 15-char IP overflows the 30 columns.
    line2 = "IP: {} / {} dBm".format(ip, rssi_text)

    return ("SSID: ", str(ssid), st7789.GREEN), line2


class Display:
    def __init__(self):
        # KEEP THE KNOWN-GOOD CONFIGURATION.
        self.spi = SPI(
            2,
            baudrate=20_000_000,
            polarity=1,
            phase=1,
            sck=Pin(TFT_SCLK),
            mosi=Pin(TFT_MOSI),
            miso=None,
        )

        self.tft = st7789.ST7789(
            self.spi,
            TFT_WIDTH,
            TFT_HEIGHT,
            reset=Pin(TFT_RST, Pin.OUT),
            dc=Pin(TFT_DC, Pin.OUT),
            cs=Pin(TFT_CS, Pin.OUT),
            rotation=0,
            color_order=st7789.BGR,
        )

        self.clear()

    def clear(self):
        self.tft.fill(st7789.BLACK)

    def text(self, message, x, y, color=st7789.WHITE):
        self.tft.text(
            font,
            str(message),
            x,
            y,
            color,
            st7789.BLACK,
        )

    def line(self, y, color=st7789.WHITE):
        self.tft.hline(
            0,
            y,
            TFT_WIDTH,
            color,
        )

    def show_header(self):
        self.text(
            "BUDDY",
            4,
            4,
            st7789.CYAN,
        )

        self.line(24, st7789.WHITE)

    def show_link(self, link):
        """Draw the Wi-Fi Link lines. Clears only its own two rows."""

        self.tft.fill_rect(
            0,
            LINE_1_Y,
            TFT_WIDTH,
            LINE_2_Y + font.HEIGHT - LINE_1_Y,
            st7789.BLACK,
        )

        (label, value, color), line2 = link_lines(link)

        self.text(label, 4, LINE_1_Y)
        self.text(value, 4 + len(label) * font.WIDTH, LINE_1_Y, color)

        if line2 is not None:
            self.text(line2, 4, LINE_2_Y)

    def show_message(self, text):
        """Draw a Message below the Wi-Fi lines. Empty text clears the area."""

        self.tft.fill_rect(
            0,
            MESSAGE_Y,
            TFT_WIDTH,
            MESSAGE_ROWS * font.HEIGHT,
            st7789.BLACK,
        )

        for i, line in enumerate(wrap(str(text), MESSAGE_COLS)[:MESSAGE_ROWS]):
            self.text(line, 4, MESSAGE_Y + i * font.HEIGHT, st7789.YELLOW)

    def show_relay(self, up):
        """Draw the Relay state bottom-left, beside the Heartbeat."""

        self.tft.fill_rect(0, RELAY_Y, 140, font.HEIGHT, st7789.BLACK)
        self.text("RELAY ", 4, RELAY_Y)
        self.text(
            "UP" if up else "DOWN",
            4 + 6 * font.WIDTH,
            RELAY_Y,
            st7789.GREEN if up else st7789.RED,
        )

    def show_animation(self, frame):
        """
        Small persistent activity indicator.

        Only redraws the animation region.
        """

        x_start = 144
        y = 212
        spacing = 10
        count = 8

        self.tft.fill_rect(
            x_start,
            204,
            96,
            36,
            st7789.BLACK,
        )

        for i in range(count):
            x = x_start + (i * spacing)

            if i == frame:
                self.tft.fill_rect(
                    x,
                    y,
                    6,
                    6,
                    st7789.GREEN,
                )
            else:
                self.tft.fill_rect(
                    x,
                    y,
                    3,
                    3,
                    st7789.WHITE,
                )


display = Display()
