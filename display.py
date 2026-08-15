from machine import Pin, SPI
import st7789py as st7789
import vga1_8x8 as font


# Hermes TFT pin assignment
TFT_MOSI = 11
TFT_SCLK = 12
TFT_CS = 8
TFT_DC = 9
TFT_RST = 10

TFT_WIDTH = 240
TFT_HEIGHT = 240

# Claude state shares the header row, to the right of the "HERMES" label.
STATUS_X = 64


STATE_COLORS = {
    "working": st7789.YELLOW,
    "idle": st7789.GREEN,
    "needs you": st7789.RED,
    "sleeping": st7789.BLUE,
}


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
            "HERMES",
            4,
            4,
            st7789.CYAN,
        )

        self.line(16, st7789.WHITE)

    def show_status(self, state):
        """
        Persistent agent state, right of the header. Redraws only its own strip.
        """

        self.tft.fill_rect(
            STATUS_X,
            0,
            TFT_WIDTH - STATUS_X,
            14,
            st7789.BLACK,
        )

        if not state:
            return

        self.text(
            str(state).upper()[:21],
            STATUS_X,
            4,
            STATE_COLORS.get(str(state).lower(), st7789.WHITE),
        )

    def show_wifi(self, ssid, ip, status, rssi=None):
        self.text("WiFi", 4, 28, st7789.CYAN)

        self.text("SSID:", 4, 44)
        self.text(str(ssid), 48, 44)

        self.text("IP:", 4, 60)
        self.text(str(ip), 48, 60)

        self.text("STATUS:", 4, 76)

        if status:
            self.text(
                "CONNECTED",
                64,
                76,
                st7789.GREEN,
            )
        else:
            self.text(
                "OFFLINE",
                64,
                76,
                st7789.RED,
            )

        if rssi is not None:
            self.text("RSSI:", 4, 92)
            self.text(
                "{} dBm".format(rssi),
                48,
                92,
            )

    def show_ping(self, result):
        """
        Display the latest ping statistics.
        """

        self.tft.fill_rect(
            0,
            112,
            TFT_WIDTH,
            128,
            st7789.BLACK,
        )

        self.text(
            "PING 1.1.1.1",
            4,
            116,
            st7789.CYAN,
        )

        # Last packet
        self.text("LAST:", 4, 132)

        if result["last_ms"] is not None:
            self.text(
                "{:.1f} ms".format(result["last_ms"]),
                48,
                132,
                st7789.GREEN,
            )

            self.text(
                "TTL {}".format(result["last_ttl"]),
                120,
                132,
            )
        else:
            self.text(
                "TIMEOUT",
                48,
                132,
                st7789.RED,
            )

        # Average
        self.text("AVG:", 4, 148)

        if result["avg_ms"] is not None:
            self.text(
                "{:.1f} ms".format(result["avg_ms"]),
                48,
                148,
            )
        else:
            self.text("--", 48, 148)

        # Min
        self.text("MIN:", 4, 164)

        if result["min_ms"] is not None:
            self.text(
                "{:.1f}".format(result["min_ms"]),
                48,
                164,
            )
        else:
            self.text("--", 48, 164)

        # Max
        self.text("MAX:", 120, 164)

        if result["max_ms"] is not None:
            self.text(
                "{:.1f}".format(result["max_ms"]),
                168,
                164,
            )
        else:
            self.text("--", 168, 164)

        # Packet loss
        self.text("LOSS:", 4, 180)

        loss = result["loss"]

        if loss == 0:
            loss_color = st7789.GREEN
        elif loss < 20:
            loss_color = st7789.YELLOW
        else:
            loss_color = st7789.RED

        self.text(
            "{:.1f}%".format(loss),
            48,
            180,
            loss_color,
        )

        # Jitter
        self.text("JITTER:", 120, 180)

        if result["jitter_ms"] is not None:
            self.text(
                "{:.2f} ms".format(result["jitter_ms"]),
                176,
                180,
            )
        else:
            self.text("--", 176, 180)

        # TTL
        self.text("TTL:", 4, 196)

        if result["avg_ttl"] is not None:
            self.text(
                "{:.0f}".format(result["avg_ttl"]),
                48,
                196,
            )
        else:
            self.text("--", 48, 196)

        # Packets
        self.text("PKT:", 120, 196)

        self.text(
            "{}/{}".format(
                result["received"],
                result["sent"],
            ),
            152,
            196,
        )

    def show_next_ping(self, seconds):
        """
        Show countdown in the bottom status area.
        """

        # Only clear the countdown area.
        self.tft.fill_rect(
            0,
            204,
            TFT_WIDTH,
            36,
            st7789.BLACK,
        )

        self.text(
            "NEXT PING",
            4,
            208,
            st7789.CYAN,
        )

        self.text(
            "{}s".format(seconds),
            88,
            208,
        )

    def show_message(self, text, title="HERMES MESSAGE"):
        """
        Full-screen takeover for an incoming ntfy message.
        """

        self.clear()

        self.text(title, 4, 4, st7789.YELLOW)
        self.line(16, st7789.WHITE)

        y = 28

        for line in wrap(str(text), 29):
            if y > 230:
                break

            self.text(line, 4, y)
            y += 12

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
