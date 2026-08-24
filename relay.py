import ssl
import time

import ntptime

from umqtt.simple import MQTTClient

from secrets import MQTT_HOST, MQTT_USER, MQTT_PASS
from led import parse_color


TOPIC_MESSAGE = b"bud/msg"
TOPIC_LED = b"bud/led"
TOPICS = (TOPIC_MESSAGE, TOPIC_LED)

CA_FILE = "lib/isrg-root-x1.pem"  # Let's Encrypt root; HiveMQ Cloud chains to it.

KEEPALIVE_S = 60
PING_MS = 30_000


def parse_payload(topic, msg):
    """('message', text) / ('led', rgb-or-None) / None for unknown topic."""

    text = msg.decode("utf-8", "ignore").strip() if isinstance(msg, bytes) else str(msg).strip()

    if topic == TOPIC_MESSAGE:
        return ("message", text)

    if topic == TOPIC_LED:
        return ("led", None if text.lower() == "off" else parse_color(text))

    return None


class Relay:
    """Retained Message / LED from the broker. Polled from the main loop."""

    def __init__(self, on_message, led):
        self.on_message = on_message
        self.led = led
        self.client = None
        self.next_ping = 0
        self.pending_ack = None  # (ack_topic, payload) set on render, sent by poll()
        self.rx_at = None  # ticks_ms of the last receive / ack send, for the
        self.tx_at = None  # Relay state dot's flashes

    def connect(self):
        """Blocking (NTP + TLS handshake, seconds). Call only while Wi-Fi Link is up."""

        try:
            # Certificate checks need a real clock; the chip boots at the epoch.
            if time.localtime()[0] < 2025:
                ntptime.settime()

            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ctx.verify_mode = ssl.CERT_REQUIRED
            ctx.load_verify_locations(cafile=CA_FILE)

            client = MQTTClient(
                b"buddy-terminal",
                MQTT_HOST,
                port=8883,
                user=MQTT_USER,
                password=MQTT_PASS,
                keepalive=KEEPALIVE_S,
                ssl=ctx,
            )
            client.set_callback(self._on_publish)
            client.connect()
            for topic in TOPICS:
                client.subscribe(topic)
        except Exception as e:  # OSError, ValueError (cert/clock), MQTTException
            print("[Relay] connect failed:", e)
            return False

        self.client = client
        self.next_ping = time.ticks_add(time.ticks_ms(), PING_MS)
        print("[Relay] connected to", MQTT_HOST)
        return True

    def poll(self):
        if self.client is None:
            return

        try:
            self.client.check_msg()

            # Receipt: publish after check_msg() returns, never on the socket
            # mid-receive. Non-retained so a fresh subscriber never sees a
            # stale ack; nobody's listening on a reconnect replay, harmless.
            if self.pending_ack is not None:
                topic, payload = self.pending_ack
                self.pending_ack = None
                self.client.publish(topic, payload, retain=False)
                self.tx_at = time.ticks_ms()

            if time.ticks_diff(time.ticks_ms(), self.next_ping) >= 0:
                self.client.ping()
                self.next_ping = time.ticks_add(time.ticks_ms(), PING_MS)
        except OSError as e:
            print("[Relay] dropped:", e)
            self.client = None
            self.pending_ack = None

    def _on_publish(self, topic, msg):
        self.rx_at = time.ticks_ms()

        parsed = parse_payload(topic, msg)

        if parsed is None:
            return

        kind, value = parsed

        if kind == "message":
            self.on_message(value)
            print("[Relay] message:", value)
            rendered = value  # already stripped by parse_payload

        elif kind == "led":
            if value is None:
                self.led.off()
            else:
                self.led.set(value)
            print("[Relay] led:", self.led.color)
            rendered = self.led.color or "off"

        # Receipt: echo what was rendered on <topic>/ack (sent by poll()).
        self.pending_ack = (topic + b"/ack", rendered.encode())
