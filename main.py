import time

import config
from wifi import wifi
from display import display
from web import WebServer
from led import led
from ping import Pinger
from relay import Relay, TOPICS


# How often the Page re-reads the Wi-Fi Link (SSID / IP / RSSI).
LINK_POLL_MS = 5_000

# How often the Terminal retries joining while it has no link. wifi.connect()
# blocks (scan + up to WIFI_CONNECT_TIMEOUT per candidate), so not every poll.
RECONNECT_MS = 30_000

ANIMATION_INTERVAL_MS = 100

# RSSI wobbles +-1 dBm between reads; only a move this big repaints the Page.
RSSI_STEP_DBM = 3


def link_changed(new, shown):
    """True when the Page should repaint for `new` given what it shows."""

    if new is None or shown is None:
        return new != shown

    if new[0] != shown[0] or new[1] != shown[1]:
        return True

    if new[2] is None or shown[2] is None:
        return new[2] != shown[2]

    return abs(new[2] - shown[2]) >= RSSI_STEP_DBM


def read_link():
    """(ssid, ip, rssi) while joined, else None."""

    if not wifi.is_connected():
        return None

    ip, _subnet = wifi.wlan.ipconfig("addr4")

    try:
        rssi = wifi.wlan.status("rssi")
    except Exception:
        rssi = None

    return wifi.get_ssid(), ip, rssi


# ----------------------------------------------------------------------
# Startup
# ----------------------------------------------------------------------

display.clear()
display.show_header()

print("Starting...")
display.text("Starting...", 4, 36)

time.sleep(1)

if wifi.is_connected():
    print("WiFi: already connected")
elif wifi.connect():
    print("WiFi: connected")
else:
    print("WiFi: connection failed")

now = time.ticks_ms()

shown_link = read_link()
display.show_link(shown_link)

print("[Display]", "Wi-Fi Link displayed" if shown_link else "Disconnected")

boot_tick = now


def status():
    return {
        "link": shown_link,
        "uptime_s": time.ticks_diff(time.ticks_ms(), boot_tick) // 1000,
        "led": led.color,
        "relay": relay.client is not None,
        "topics": [t.decode() for t in TOPICS] if relay.client else [],
        "ping": pinger.stats,
    }


pinger = Pinger(config.PING_TARGET)
relay = Relay(display.show_message, led)
web = WebServer(status, display.show_message, led)

def relay_lines():
    """(sub, pub) for the Relay block."""

    up = relay.client is not None
    sub = ",".join(t.decode() for t in TOPICS) if up else "-"
    pub = ",".join(t.decode() + "/ack" for t in TOPICS) if up else "-"  # Receipts
    return sub, pub


shown_relay = False
display.show_relay(*relay_lines())  # topics only; state is the dot

if shown_link:
    print("[Web] http://{}/".format(shown_link[1]))

next_poll = time.ticks_add(now, LINK_POLL_MS)
last_connect_attempt = now
last_relay_attempt = now - RECONNECT_MS  # try on first poll
next_animation = now
animation_frame = 0

# Relay state dot: rx/tx events flash yellow/blue for FLASH_MS each, queued
# so the ack's blue is not swallowed by the receive's yellow.
FLASH_MS = 600
flash_queue = []
flash_state = None
flash_until = 0
seen_rx = None
seen_tx = None


# ----------------------------------------------------------------------
# Main loop
# ----------------------------------------------------------------------

while True:

    now = time.ticks_ms()

    # --------------------------------------------------------------
    # Wi-Fi Link: redraw on change, rejoin while down
    # --------------------------------------------------------------

    if time.ticks_diff(now, next_poll) >= 0:

        next_poll = time.ticks_add(now, LINK_POLL_MS)

        link = read_link()

        if link is None and time.ticks_diff(now, last_connect_attempt) >= RECONNECT_MS:
            last_connect_attempt = now

            if wifi.connect():
                link = read_link()

            # connect() blocked for seconds; don't replay the missed frames.
            now = time.ticks_ms()
            next_animation = now

        if link_changed(link, shown_link):
            if (link is None) != (shown_link is None):
                pinger.reset()  # fresh window for the new link state
                display.show_ping(None)

            shown_link = link
            display.show_link(link)
            print("[Display]", link if link else "Disconnected")

    # --------------------------------------------------------------
    # Ping: probe while the Link is up, repaint when a batch lands
    # --------------------------------------------------------------

    if shown_link and pinger.poll(now):
        display.show_ping(pinger.stats)

    web.poll()

    # --------------------------------------------------------------
    # Relay: connect while the Link is up, then poll for retained
    # Message / LED. connect() blocks for the TLS handshake (seconds),
    # so it runs on the Wi-Fi retry cadence, never every tick.
    # --------------------------------------------------------------

    if relay.client is None and shown_link and time.ticks_diff(now, last_relay_attempt) >= RECONNECT_MS:
        last_relay_attempt = now
        relay.connect()
        now = time.ticks_ms()
        next_animation = now

    relay.poll()

    if (relay.client is not None) != shown_relay:
        shown_relay = relay.client is not None
        display.show_relay(*relay_lines())

    # --------------------------------------------------------------
    # Relay state dot (doubles as the Heartbeat)
    # --------------------------------------------------------------

    # Relay state dot: pick up new rx/tx events, run the flash queue.
    if relay.rx_at != seen_rx:
        seen_rx = relay.rx_at
        flash_queue.append("rx")

    if relay.tx_at != seen_tx:
        seen_tx = relay.tx_at
        flash_queue.append("tx")

    if flash_state is not None and time.ticks_diff(now, flash_until) >= 0:
        flash_state = None

    if flash_state is None and flash_queue:
        flash_state = flash_queue.pop(0)
        flash_until = time.ticks_add(now, FLASH_MS)

    if time.ticks_diff(now, next_animation) >= 0:

        display.show_relay_dot(
            animation_frame,
            flash_state or ("up" if relay.client else "down"),
        )

        animation_frame += 1

        if animation_frame >= 20:  # multiple of the dot's 4-frame flicker
            animation_frame = 0

        next_animation = time.ticks_add(
            next_animation,
            ANIMATION_INTERVAL_MS,
        )

    time.sleep_ms(20)
