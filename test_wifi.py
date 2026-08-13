# Runs on CPython too: pick_networks is pure. `python3 test_wifi.py`
import sys
import types

# wifi.py imports MicroPython/device modules at import time
network = types.ModuleType("network")
network.WLAN = lambda *a, **kw: None
network.WLAN.IF_STA = 0
sys.modules["network"] = network
secrets = types.ModuleType("secrets")
secrets.WIFI_NETWORKS = []
sys.modules["secrets"] = secrets

from wifi import pick_networks


KNOWN = [("Wifi-1", "p1"), ("Wifi-2", "p2"), ("Wifi-3", "p3")]


def ap(ssid, rssi):
    return (ssid.encode(), b"\x00" * 6, 1, rssi, 3, False)


def test():
    # strongest known first, unknown SSIDs dropped
    result = pick_networks(
        [ap("Wifi-2", -80), ap("Neighbour", -30), ap("Wifi-3", -45)], KNOWN
    )
    assert result == [("Wifi-3", "p3", -45), ("Wifi-2", "p2", -80)], result

    # duplicate SSID (repeater): strongest AP wins
    result = pick_networks([ap("Wifi-1", -70), ap("Wifi-1", -40)], KNOWN)
    assert result == [("Wifi-1", "p1", -40)], result

    # nothing known in range
    assert pick_networks([ap("Neighbour", -30)], KNOWN) == []

    print("ok")


test()
