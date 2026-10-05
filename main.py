import time

import ntptime

import config
from wifi import wifi
from display import display
from web import WebServer
from led import led
from ping import Pinger
from history import History
from relay import Relay, TOPICS, TOPIC_PING


# How often the Page re-reads the Wi-Fi Link (SSID / IP / RSSI).
LINK_POLL_MS = 5_000

# How often the Terminal retries joining while it has no link. wifi.connect()
# blocks (scan + up to WIFI_CONNECT_TIMEOUT per candidate), so not every poll.
RECONNECT_MS = 30_000

ANIMATION_INTERVAL_MS = 100

# RSSI wobbles +-1 dBm between reads; only a move this big repaints the Page.
RSSI_STEP_DBM = 3

# Clock: NTP on link-up, then every 6 h; retry each minute until it lands.
NTP_OK_MS = 6 * 3600_000
NTP_RETRY_MS = 60_000


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
        "history": history.count,
        "mac": relay.mac_listening,
    }


def push():
    """Control Page button: (ok, text). The drain itself is the auto rule below."""

    if relay.client is None:
        return False, "Relay down"
    if not relay.mac_listening:
        return False, "Mac not listening"
    if not history.count:
        return True, "Nothing to push"
    return True, "Pushing {}".format(history.count)


pinger = Pinger(config.PING_TARGET)
history = History()
relay = Relay(display.show_message, led)
web = WebServer(status, display.show_message, led, push)


def online():
    """Internet reachable: a link and the latest Ping batch not fully lost."""

    if shown_link is None:
        return False
    return pinger.stats is None or pinger.stats[0] is not None


def local_time():
    """time.localtime() shifted to config.TZ_OFFSET_MIN, or None before sync."""

    if time.localtime()[0] < 2025:
        return None
    return time.localtime(time.time() + config.TZ_OFFSET_MIN * 60)


shown_online = True  # show_header() drew cyan
shown_clock = None
display.show_clock(None)
shown_history = history.count
display.show_history(shown_history)
next_ntp = now  # first sync as soon as the link is up

if shown_link:
    print("[Web] http://{}/".format(shown_link[1]))

next_poll = time.ticks_add(now, LINK_POLL_MS)
last_connect_attempt = now
last_relay_attempt = now - RECONNECT_MS  # try on first poll
next_animation = now
animation_frame = 0

# Relay state dot: rx/tx events flash yellow/blue for FLASH_MS each, queued
# so the ack's blue is not swallowed by the receive's yellow.
FLASH_MS = 800
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
    # Ping: probe while the Link is up; repaint and record the batch
    # when one lands
    # --------------------------------------------------------------

    if shown_link and pinger.poll(now):
        display.show_ping(pinger.stats)
        history.record(pinger.stats)

    history.poll(now)

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

    # --------------------------------------------------------------
    # History: drain one chunk per tick while the Mac is listening.
    # A chunk already handed to the socket when the Relay drops is
    # lost (<= CHUNK records); the rest goes back to the store.
    # --------------------------------------------------------------

    if relay.client and relay.mac_listening:
        if history.count and not relay.pending:
            relay.publish(TOPIC_PING, history.next_chunk())
    elif history.pending:
        history.abort()

    relay.poll()

    if history.count != shown_history:
        shown_history = history.count
        display.show_history(shown_history)

    # --------------------------------------------------------------
    # "Buddy" colour: internet reach
    # --------------------------------------------------------------

    if online() != shown_online:
        shown_online = online()
        display.show_header(shown_online)

    # --------------------------------------------------------------
    # Clock: NTP sync while the Link is up, repaint each second
    # --------------------------------------------------------------

    if shown_link and time.ticks_diff(now, next_ntp) >= 0:
        try:
            ntptime.settime()
            next_ntp = time.ticks_add(now, NTP_OK_MS)
            print("[Clock] synced")
        except Exception as e:
            next_ntp = time.ticks_add(now, NTP_RETRY_MS)
            print("[Clock] NTP failed:", e)
        now = time.ticks_ms()  # settime() blocks up to a second

    local = local_time()
    if local is not None:
        local = local[:6]
    if local != shown_clock:
        shown_clock = local
        display.show_clock(local)

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

        if animation_frame >= 20:  # multiple of the dot's 10-frame blink
            animation_frame = 0

        next_animation = time.ticks_add(
            next_animation,
            ANIMATION_INTERVAL_MS,
        )

    time.sleep_ms(20)
