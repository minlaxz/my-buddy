
import time
import network

from secrets import WIFI_SSID, WIFI_PASSWORD
from config import (
    WIFI_CONNECT_TIMEOUT,
    WIFI_RETRY_DELAY,
)


class WiFiManager:
    def __init__(self):
        self.wlan = network.WLAN(network.WLAN.IF_STA)

    def activate(self):
        if not self.wlan.active():
            self.wlan.active(True)

    def is_connected(self):
        return self.wlan.isconnected()

    def get_ssid(self):
        return WIFI_SSID

    def connect(self):
        self.activate()

        if self.is_connected():
            print("[WiFi] Already connected")
            self.print_info()
            return True

        print("[WiFi] Connecting to:", WIFI_SSID)

        self.wlan.connect(WIFI_SSID, WIFI_PASSWORD)

        start = time.ticks_ms()
        timeout = WIFI_CONNECT_TIMEOUT * 1000

        while not self.wlan.isconnected():
            elapsed = time.ticks_diff(time.ticks_ms(), start)

            if elapsed >= timeout:
                print("[WiFi] Connection timeout")
                print("[WiFi] Status:", self.wlan.status())
                return False

            print("[WiFi] Waiting...")
            time.sleep(1)

        print("[WiFi] Connected")
        self.print_info()

        return True

    def print_info(self):
        print("[WiFi] IP:", self.wlan.ipconfig("addr4"))
        print("[WiFi] Status:", self.wlan.status())

    def reconnect(self):
        print("[WiFi] Reconnecting...")

        try:
            self.wlan.disconnect()
        except Exception:
            pass

        time.sleep(WIFI_RETRY_DELAY)

        return self.connect()


wifi = WiFiManager()
