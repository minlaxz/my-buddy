"""Self-check for Relay payload parsing. Run on host: python3 tests/test_relay.py"""

import os
import sys
import types

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))  # relay.py lives at the repo root

# Stub device-only modules so relay.py imports on a host Python.
import time

for n in ("ticks_ms", "ticks_add", "ticks_diff"):
    setattr(time, n, lambda *a: 0)  # host time has no ticks

sys.modules["ssl"] = types.ModuleType("ssl")
sys.modules["ntptime"] = types.ModuleType("ntptime")
sys.modules["umqtt"] = types.ModuleType("umqtt")
sys.modules["umqtt.simple"] = types.SimpleNamespace(MQTTClient=object)
sys.modules["secrets"] = types.SimpleNamespace(MQTT_HOST="h", MQTT_USER="u", MQTT_PASS="p")
class _Pin:
    OUT = 1
    def __init__(self, *a): pass

class _Pixel:
    def __init__(self, *a): self.buf = [None]
    def __setitem__(self, i, v): self.buf[i] = v
    def write(self): pass

sys.modules["machine"] = types.SimpleNamespace(Pin=_Pin)
sys.modules["neopixel"] = types.SimpleNamespace(NeoPixel=_Pixel)

from relay import Relay, parse_payload, TOPIC_MESSAGE, TOPIC_LED, TOPIC_PING, TOPIC_HISTORY

assert parse_payload(TOPIC_MESSAGE, b"hello") == ("message", "hello")
assert parse_payload(TOPIC_MESSAGE, b"  spaced \n") == ("message", "spaced")
assert parse_payload(TOPIC_MESSAGE, b"") == ("message", "")
assert parse_payload(TOPIC_LED, b"#ff0000") == ("led", (255, 0, 0))
assert parse_payload(TOPIC_LED, b"00ff00") == ("led", (0, 255, 0))
assert parse_payload(TOPIC_LED, b"off") == ("led", None)
assert parse_payload(TOPIC_LED, b"OFF") == ("led", None)
assert parse_payload(TOPIC_LED, b"nope") == ("led", None)
assert parse_payload(TOPIC_HISTORY, b"on") == ("history", True)
assert parse_payload(TOPIC_HISTORY, b"off") == ("history", False)
assert parse_payload(b"buddy/other", b"x") is None

# publish(): dropped while down, queued while up, drained in order by poll().
sent = []
r = Relay(lambda m: None, None)
r.publish(TOPIC_PING, b"x")
assert r.pending == []
r.client = types.SimpleNamespace(check_msg=lambda: None, ping=lambda: None, publish=lambda t, p, retain: sent.append((t, p)))
r.publish(TOPIC_PING, b"1")
r.publish(TOPIC_LED + b"/ack", b"2")
r.poll()
assert sent == [(TOPIC_PING, b"1"), (TOPIC_LED + b"/ack", b"2")] and r.pending == []

# bud/history flips mac_listening and earns no Receipt.
r._on_publish(TOPIC_HISTORY, b"on")
assert r.mac_listening and r.pending == []
r._on_publish(TOPIC_HISTORY, b"off")
assert not r.mac_listening

print("ok")
