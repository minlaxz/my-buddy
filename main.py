import time

from wifi import wifi
from display import display


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

next_poll = time.ticks_add(now, LINK_POLL_MS)
last_connect_attempt = now
next_animation = now
animation_frame = 0


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
            shown_link = link
            display.show_link(link)
            print("[Display]", link if link else "Disconnected")

    # --------------------------------------------------------------
    # Persistent animation
    # --------------------------------------------------------------

    if time.ticks_diff(now, next_animation) >= 0:

        display.show_animation(animation_frame)

        animation_frame += 1

        if animation_frame >= 8:
            animation_frame = 0

        next_animation = time.ticks_add(
            next_animation,
            ANIMATION_INTERVAL_MS,
        )

    time.sleep_ms(20)
