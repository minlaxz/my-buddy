# Copy to secrets.py (gitignored) and fill in. Upload secrets.py to the device.
# Order does not matter: the strongest network in range wins.
WIFI_NETWORKS = [
    ("Wifi-1", "room-password"),
    ("Wifi-2", "guest-password"),
    ("Wifi-3", "office-password"),
]

# Relay: HiveMQ Cloud cluster and the subscribe-only "terminal" credential.
MQTT_HOST = "xxxxxxxx.s1.eu.hivemq.cloud"
MQTT_USER = "terminal"
MQTT_PASS = "terminal-password"
