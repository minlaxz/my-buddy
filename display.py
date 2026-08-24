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

# Header line: "Buddy", Ping stats, Relay state dot in the top-right corner.
PING_X = 4 + 6 * 8  # after "Buddy" + one space, font.WIDTH = 8
PING_Y = 4

# Message area: below the Wi-Fi lines, down to just above the Clock row.
MESSAGE_Y = 76
MESSAGE_ROWS = 8  # 76 + 8*16 = 204, clears CLOCK_Y = 208
MESSAGE_COLS = 29

# Clock: bottom row, "YYYY-MM-DD HH:MM:SS" in local time.
CLOCK_Y = 208

# Relay state dot: top-right corner, blinks 1 Hz; colour = state.
# It doubles as the Heartbeat — a frozen dot means a hung loop.
RELAY_DOT_X = TFT_WIDTH - 12
RELAY_DOT_Y = 8
RELAY_DOT_COLORS = {
    "up": st7789.GREEN,
    "down": st7789.RED,
    "rx": st7789.YELLOW,  # receiving from the Relay
    "tx": st7789.BLUE,  # sending to the Relay (Receipt ack)
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
    line2 = "IP: {} / {:<4} dBm".format(ip, rssi_text)  # pad: see show_link

    return ("SSID: ", str(ssid), st7789.GREEN), line2


class Display:
    def __init__(self):
        self._clock_head = None  # show_clock: last drawn date+hh:mm
        self._link_head = None  # show_link: last drawn (ssid, ip)

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

    def show_header(self, online=True):
        """"Buddy": cyan while the internet is reachable, red while not."""

        self.text("Buddy", 4, 4, st7789.CYAN if online else st7789.RED)
        self.line(24, st7789.WHITE)

    def show_link(self, link):
        """Draw the Wi-Fi Link lines. If only the RSSI moved since the last
        draw, repaint just the "-46 dBm" cell; otherwise clear both rows."""

        head = None if link is None else link[:2]  # (ssid, ip)

        if link is not None and head == self._link_head:
            rssi_text = "--" if link[2] is None else str(link[2])
            x = 4 + len("IP: {} / ".format(link[1])) * font.WIDTH
            # text() paints its own background; pad so "-46" over "-100" clears.
            self.text("{:<4} dBm".format(rssi_text), x, LINE_2_Y)
            return

        self._link_head = head

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

    def show_ping(self, stats):
        """Draw the Ping stats on the header line, beside "Buddy". None clears.

        stats: (avg_ms, loss_pct, jitter_ms); avg/jitter are None when the
        whole batch was lost.
        """

        # Stop short of the Relay state dot.
        self.tft.fill_rect(
            PING_X, PING_Y, RELAY_DOT_X - 4 - PING_X, font.HEIGHT, st7789.BLACK
        )

        if stats is None:
            return

        avg, loss, jitter = stats

        # Loss tiers: clean green, degraded yellow, bad red.
        if loss == 0:
            loss_color = st7789.GREEN
        elif loss <= 20:
            loss_color = st7789.YELLOW
        else:
            loss_color = st7789.RED

        # Jitter tiers from VoIP guidance: <=20 ms fine, <=30 ms edge, above bad.
        if jitter is None:
            jitter_color = st7789.WHITE
        elif jitter <= 20:
            jitter_color = st7789.GREEN
        elif jitter <= 30:
            jitter_color = st7789.YELLOW
        else:
            jitter_color = st7789.RED

        # No "PING:" label — compact so worst case (999ms L:100% J:999ms,
        # 20 chars) still clears the Heartbeat dot.
        segments = (
            (("--" if avg is None else "{}ms".format(avg)) + " ", st7789.WHITE),
            ("L:{}% ".format(loss), loss_color),
            ("J:--" if jitter is None else "J:{}ms".format(jitter), jitter_color),
        )

        x = PING_X
        for part, color in segments:
            self.text(part, x, PING_Y, color)
            x += len(part) * font.WIDTH

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

    def show_clock(self, local):
        """Draw the Clock row. local: time tuple already offset, or None for
        "--:--" before the first sync. Repaints only the cells that changed:
        the seconds every tick, the rest once a minute."""

        if local is None:
            self.tft.fill_rect(0, CLOCK_Y, TFT_WIDTH, font.HEIGHT, st7789.BLACK)
            self.text("--:--", 4, CLOCK_Y)
            self._clock_head = None
            return

        y, mo, d, h, mi, s = local[:6]
        head = "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:".format(y, mo, d, h, mi)

        if head != self._clock_head:
            self._clock_head = head
            self.tft.fill_rect(0, CLOCK_Y, TFT_WIDTH, font.HEIGHT, st7789.BLACK)
            self.text(head, 4, CLOCK_Y)

        # text() paints its own background, so no clear for the seconds cell.
        self.text("{:02d}".format(s), 4 + len(head) * font.WIDTH, CLOCK_Y)

    def show_relay_dot(self, frame, state):
        """Flickering Relay state dot, top-right of the header line.

        state: "up" / "down" / "rx" / "tx". Blinks 1 Hz on up/down (a
        frozen dot means a hung loop); rx/tx hold solid so the flash is
        never swallowed by an off phase.
        """

        on = state in ("rx", "tx") or frame % 10 < 5
        color = RELAY_DOT_COLORS[state]
        self.tft.fill_rect(
            RELAY_DOT_X, RELAY_DOT_Y, 8, 8, color if on else st7789.BLACK
        )


display = Display()
