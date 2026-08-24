"""Self-check for Relay payload parsing. Run on host: python3 test_relay.py"""

import sys
import types

# Stub device-only modules so relay.py imports on a host Python.
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

from relay import parse_payload, TOPIC_MESSAGE, TOPIC_LED

assert parse_payload(TOPIC_MESSAGE, b"hello") == ("message", "hello")
assert parse_payload(TOPIC_MESSAGE, b"  spaced \n") == ("message", "spaced")
assert parse_payload(TOPIC_MESSAGE, b"") == ("message", "")
assert parse_payload(TOPIC_LED, b"#ff0000") == ("led", (255, 0, 0))
assert parse_payload(TOPIC_LED, b"00ff00") == ("led", (0, 255, 0))
assert parse_payload(TOPIC_LED, b"off") == ("led", None)
assert parse_payload(TOPIC_LED, b"OFF") == ("led", None)
assert parse_payload(TOPIC_LED, b"nope") == ("led", None)
assert parse_payload(b"buddy/other", b"x") is None

print("ok")
