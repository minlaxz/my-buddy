# Buddy

A physical ESP32-S3 + 240x240 TFT unit on the owner's desk. Today it shows which Wi-Fi network it is on, its address and signal strength, and any Message pushed to it from its Control Page or through the Relay; the LED is set the same two ways. Anything beyond that is not yet decided and not in this glossary.

## Language

**Buddy**:
The desk unit and its firmware, as a whole. There is no second part today.
_Avoid_: Hermes (the old name), my-buddy (repo name only)

**Terminal**:
The physical ESP32-S3 + TFT unit, and the MicroPython firmware it runs. This repo is the Terminal's code. Today Buddy and the Terminal are the same thing; the word exists so that Buddy can grow a second part without renaming this one.
_Avoid_: the board, the device, ESP32 (that's the chip, not the role)

**Capability**:
A distinct thing the Terminal can do for its owner. Today: showing the Wi-Fi Link, showing a Message, lighting the LED.

**Page**:
A full-screen view owned by one Capability. With one Capability there is one Page, shown permanently.
_Avoid_: screen, dashboard, view

**Wi-Fi Link**:
What the one Page shows: the SSID the Terminal is joined to, its IP and its RSSI. When the Terminal is not joined to any known network the Page says so instead, and the Terminal keeps trying to join.
_Avoid_: connection status, network info

**Ping**:
A line on the Page under the Wi-Fi Link showing round-trip quality to the internet: average time and jitter over the latest few probes, loss over a longer rolling window. Blank while the Terminal has no link; dashes when nothing comes back at all. Also shown on the Control Page.
_Avoid_: latency check, ICMP (implementation detail), Heartbeat (that's the loop-alive dot)

**Control Page**:
The web page the Terminal serves at its own LAN address. The owner reads the Wi-Fi Link there and sets the Message and the LED, or reboots. Reachable only from the same network; it trusts anyone on it.
_Avoid_: dashboard, admin, API (the JSON behind it is an implementation detail)

**Relay**:
The way to reach the Terminal from beyond its LAN. It holds the last Message and LED a Sender gave it, and hands them over whenever the Terminal connects to it — so a Terminal that was off or away catches up, and the Relay's last word wins over anything set on the Control Page in between. The Page and the Control Page both say whether the Terminal is currently joined to it.
_Avoid_: MQTT, HiveMQ, broker, cloud, topic

**Sender**:
Anything that pushes a Message or LED through the Relay. Today: a command-line tool on the owner's Mac. Not the Terminal, and not the Control Page.
_Avoid_: publisher, client, hook

**Receipt**:
What the Terminal sends back through the Relay the moment it shows a Message or sets the LED — an echo of what it rendered. A Sender waits a few seconds for it, so pushing a Message can tell the owner the desk unit really changed, not just that the Relay took it. Times out quietly when the Terminal is away; the last Message and LED still arrive later, the owner just did not get live word. Carries no state and is never held.
_Avoid_: ack, acknowledgement, confirmation, publish, outbound topic

**Message**:
Text pushed to the Terminal from the Control Page or by a Sender through the Relay. Drawn on the Page under the Wi-Fi Link and stays there until replaced or cleared; it never interrupts anything and never times out.
_Avoid_: notification (the old interrupting, timed thing), alert, popup

**LED**:
The onboard RGB pixel, set to a colour or off from the Control Page or by a Sender through the Relay. Holds whatever it was last set to; it means nothing on its own.
_Avoid_: Beacon (the old name — it used to mirror Claude's Status), RGB, light

**Heartbeat**:
A single dot in the bottom corner of the Page that blinks about once a second, its colour stepping red, green, blue. Says only that the firmware loop is alive; carries no data. If it freezes on one colour, the Terminal is hung.
_Avoid_: animation, spinner, activity indicator
