import time

import config
import secrets
from wifi import wifi
from display import display
from ping import ping
from ntfy import NtfyStream


PING_HOST = "1.1.1.1"

PING_INTERVAL_MS = 60_000

ANIMATION_INTERVAL_MS = 100


def log(message, line):
    print(message)
    display.text(message, 4, line * 10)


def get_wifi_info():
    if not wifi.is_connected():
        return None, None

    ip, subnet = wifi.wlan.ipconfig("addr4")

    try:
        rssi = wifi.wlan.status("rssi")
    except Exception:
        rssi = None

    return ip, rssi


def draw_normal():
    """Repaint the standard network screen (also used after a message clears)."""

    display.clear()
    display.show_header()
    display.show_status(claude_state)

    if wifi.is_connected():
        ip, rssi = get_wifi_info()

        display.show_wifi(
            ssid=wifi.get_ssid(),
            ip=ip,
            status=True,
            rssi=rssi,
        )
    else:
        display.show_wifi(
            ssid=wifi.get_ssid(),
            ip="--",
            status=False,
        )

    if ping_result is not None:
        display.show_ping(ping_result)


ping_result = None

# Sticky agent state shown in the header; survives message popups.
claude_state = None


# ----------------------------------------------------------------------
# Startup
# ----------------------------------------------------------------------

display.clear()

display.show_header()

print("Starting...")
display.text("Starting...", 4, 24)

time.sleep(1)

print("WiFi: connecting")

if wifi.is_connected():
    print("WiFi: already connected")
else:
    if wifi.connect():
        print("WiFi: connected")
    else:
        print("WiFi: connection failed")


# ----------------------------------------------------------------------
# Initial Wi-Fi display
# ----------------------------------------------------------------------

draw_normal()

if wifi.is_connected():
    print("[Display] WiFi information displayed")
else:
    print("[Display] Network unavailable")


# ----------------------------------------------------------------------
# Initial ping
# ----------------------------------------------------------------------

print("[Ping] Testing", PING_HOST)

ping_result = ping(
    host=PING_HOST,
    count=5,
    timeout=2,
    interval=0.1,
)

display.show_ping(ping_result)

print("[Display] Ping information displayed")


# ----------------------------------------------------------------------
# Timers
# ----------------------------------------------------------------------

now = time.ticks_ms()

next_ping = time.ticks_add(
    now,
    PING_INTERVAL_MS,
)

next_animation = now

animation_frame = 0

ntfy = NtfyStream(
    config.NTFY_HOST,
    config.NTFY_TOPIC,
    token=getattr(secrets, "NTFY_TOKEN", None),
)

# When set, a message is on screen until this tick.
message_until = None


# ----------------------------------------------------------------------
# Main loop
# ----------------------------------------------------------------------

last_displayed_second = -1

while True:

    now = time.ticks_ms()

    # --------------------------------------------------------------
    # ntfy stream
    # --------------------------------------------------------------

    event = ntfy.poll()

    if event:
        title, message = event

        if title == "state":
            # Sticky: updates the header, never takes over the screen.
            claude_state = message

            print("[state]", claude_state)

            if message_until is None:
                display.show_status(claude_state)

        else:
            print("[Hermes]", message)

            display.show_message(message)

            message_until = time.ticks_add(now, config.NTFY_MESSAGE_MS)

    if message_until is not None:

        if time.ticks_diff(now, message_until) < 0:
            # Message owns the screen; nothing else may draw.
            time.sleep_ms(20)
            continue

        message_until = None

        draw_normal()

        last_displayed_second = -1
        next_animation = now

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


    # --------------------------------------------------------------
    # Ping every 60 seconds
    # --------------------------------------------------------------

    if time.ticks_diff(now, next_ping) >= 0:

        print("[Ping] Testing", PING_HOST)

        ping_result = ping(
            host=PING_HOST,
            count=5,
            timeout=2,
            interval=0.1,
        )

        display.show_ping(ping_result)

        print("[Display] Ping information displayed")

        next_ping = time.ticks_add(
            now,
            PING_INTERVAL_MS,
        )


    # --------------------------------------------------------------
    # Countdown
    # --------------------------------------------------------------

    remaining_ms = time.ticks_diff(
        next_ping,
        now,
    )

    if remaining_ms < 0:
        remaining_ms = 0

    remaining_seconds = (
        remaining_ms + 999
    ) // 1000

    if remaining_seconds != last_displayed_second:
        display.show_next_ping(remaining_seconds)
        last_displayed_second = remaining_seconds

    time.sleep_ms(20)
