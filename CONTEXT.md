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
What the one Page shows: the SSID the Terminal is joined to, its IP and its RSSI. When the Terminal is not joined to any known network the Page says so instead, and the Terminal keeps trying to join. The word "Buddy" at the top of the Page is cyan while the Terminal reaches the internet and red while it does not — no link, or the latest Ping got nothing back. Not yet known counts as reachable.
_Avoid_: connection status, network info, online/offline (the Page shows the colour, not the word)

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

**History**:
The record of past Ping batches, shown as a graph in a browser. The Recorder keeps it; the Terminal keeps every batch it measures (in memory, then flash) only until the Recorder is listening, and shows how many it is holding on the Page and the Control Page. With the Recorder always on, the Terminal holds only while it cannot reach the Relay, and hands everything over the moment it can; a button on the Control Page asks for the same by hand. Gaps in the graph are honest: Terminal off, or its clock not yet set.
_Avoid_: telemetry, log, time series, dashboard, buffer, queue

**Recorder**:
The always-on service on a VPS that listens on the Relay for the Terminal's Ping batches, stores them and serves the History graph. Says it is listening through the Relay so the Terminal knows when to hand batches over. Not a Sender.
_Avoid_: receiver, backend, server, the Mac (where it used to run)

**Message**:
Text pushed to the Terminal from the Control Page or by a Sender through the Relay. Drawn on the Page under the Wi-Fi Link and stays there until replaced or cleared; it never interrupts anything and never times out.
_Avoid_: notification (the old interrupting, timed thing), alert, popup

**LED**:
The onboard RGB pixel, set to a colour or off from the Control Page or by a Sender through the Relay. Holds whatever it was last set to; it means nothing on its own.
_Avoid_: Beacon (the old name — it used to mirror Claude's Status), RGB, light

**Heartbeat**:
A single dot in the top-right corner of the Page that blinks about once a second. Its colour is the Relay: green while joined, red while it cannot be reached; it holds steady yellow for a moment when something arrives from the Relay and steady blue when a Receipt goes back. If it freezes on green or red, the Terminal is hung.
_Avoid_: animation, spinner, activity indicator, Relay dot (same thing, one name)

**Clock**:
The date and time on the bottom row of the Page, in Yangon time, ticking every second. Set from the internet once the Wi-Fi Link is up and refreshed every few hours; shows `--:--` until it has been set the first time. Keeps ticking while the Terminal is offline.
_Avoid_: RTC, NTP (how it is set), timestamp
