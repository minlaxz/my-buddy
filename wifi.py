
import time
import network

from secrets import WIFI_NETWORKS
from config import (
    WIFI_CONNECT_TIMEOUT,
    WIFI_RETRY_DELAY,
)


def pick_networks(scan_results, known):
    """Known networks in range, strongest first: [(ssid, password, rssi)]."""
    seen = {}
    for entry in scan_results:
        ssid = entry[0].decode()
        rssi = entry[3]
        # keep the strongest AP per SSID (mesh / repeaters)
        if ssid not in seen or rssi > seen[ssid]:
            seen[ssid] = rssi

    found = [
        (ssid, password, seen[ssid])
        for ssid, password in known
        if ssid in seen
    ]
    found.sort(key=lambda n: n[2], reverse=True)

    return found


class WiFiManager:
    def __init__(self):
        self.wlan = network.WLAN(network.WLAN.IF_STA)
        self.ssid = None

    def activate(self):
        if not self.wlan.active():
            self.wlan.active(True)

    def is_connected(self):
        return self.wlan.isconnected()

    def get_ssid(self):
        if self.ssid is None and self.is_connected():
            # connection survived a soft reset: ask the driver
            try:
                self.ssid = self.wlan.config("ssid")
            except Exception:
                pass

        return self.ssid or "--"

    def scan(self):
        self.activate()
        return pick_networks(self.wlan.scan(), WIFI_NETWORKS)

    def connect(self):
        self.activate()

        if self.is_connected():
            print("[WiFi] Already connected")
            self.print_info()
            return True

        candidates = self.scan()

        if not candidates:
            print("[WiFi] No known network in range")
            return False

        print("[WiFi] In range:", [(s, r) for s, _, r in candidates])

        for ssid, password, rssi in candidates:
            if self._connect_one(ssid, password):
                return True

        print("[WiFi] All known networks failed")
        return False

    def _connect_one(self, ssid, password):
        print("[WiFi] Connecting to:", ssid)

        self.wlan.connect(ssid, password)

        start = time.ticks_ms()
        timeout = WIFI_CONNECT_TIMEOUT * 1000

        while not self.wlan.isconnected():
            elapsed = time.ticks_diff(time.ticks_ms(), start)

            if elapsed >= timeout:
                print("[WiFi] Connection timeout:", ssid)
                print("[WiFi] Status:", self.wlan.status())
                try:
                    self.wlan.disconnect()
                except Exception:
                    pass
                return False

            print("[WiFi] Waiting...")
            time.sleep(1)

        self.ssid = ssid

        print("[WiFi] Connected")
        self.print_info()

        return True

    def print_info(self):
        print("[WiFi] SSID:", self.get_ssid())
        print("[WiFi] IP:", self.wlan.ipconfig("addr4"))
        print("[WiFi] Status:", self.wlan.status())

    def reconnect(self):
        print("[WiFi] Reconnecting...")

        self.ssid = None

        try:
            self.wlan.disconnect()
        except Exception:
            pass

        time.sleep(WIFI_RETRY_DELAY)

        return self.connect()


wifi = WiFiManager()
