# Buddy

A physical ESP32-S3 + 240x240 TFT unit on the owner's desk. Today it does one thing: shows which Wi-Fi network it is on, its address and signal strength. Anything beyond that is not yet decided and not in this glossary.

## Language

**Buddy**:
The desk unit and its firmware, as a whole. There is no second part today.
_Avoid_: Hermes (the old name), my-buddy (repo name only)

**Terminal**:
The physical ESP32-S3 + TFT unit, and the MicroPython firmware it runs. This repo is the Terminal's code. Today Buddy and the Terminal are the same thing; the word exists so that Buddy can grow a second part without renaming this one.
_Avoid_: the board, the device, ESP32 (that's the chip, not the role)

**Capability**:
A distinct thing the Terminal can do for its owner. There is one: showing the Wi-Fi link.

**Page**:
A full-screen view owned by one Capability. With one Capability there is one Page, shown permanently.
_Avoid_: screen, dashboard, view

**Wi-Fi Link**:
What the one Page shows: the SSID the Terminal is joined to, its IP and its RSSI. When the Terminal is not joined to any known network the Page says so instead, and the Terminal keeps trying to join.
_Avoid_: connection status, network info

**Heartbeat**:
The row of dots at the bottom of the Page with one dot hopping along it. Says only that the firmware loop is alive; carries no data. If it stops, the Terminal is hung.
_Avoid_: animation, spinner, activity indicator
