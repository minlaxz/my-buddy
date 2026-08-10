# Hermes

A personal companion system in two parts: a physical ESP32-S3 + 240x240 TFT unit on the owner's desk, and (phase 2) a personal AI agent on a VPS that uses the desk unit as its voice. Today the desk unit works as a standalone network tool.

## Language

**Hermes**:
The whole companion system — desk Terminal plus (eventually) the Agent.
_Avoid_: my-buddy (repo name only)

**Terminal**:
The physical ESP32-S3 + TFT unit on the desk, and the MicroPython firmware it runs. This repo is the Terminal's code.
_Avoid_: the board, the device, ESP32 (that's the chip, not the role)

**Hermes Agent**:
The owner's personal AI agent, living on a VPS. It does the thinking; when it wants to say something (e.g. a greeting), it pushes a Notification to the Terminal. Phase 2 — does not exist in this repo yet.
_Avoid_: server, backend

**Capability**:
A distinct thing the Terminal can do for its owner. Phase 1 has one: network monitoring.

**Page**:
A full-screen view owned by one capability. With one capability there is one Page; when several exist they rotate on a timer.
_Avoid_: screen, dashboard, view

**Notification**:
A message pushed to the Terminal from outside (the Hermes Agent, or any authorized sender). Takes over the screen, interrupting the current Page, until it times out, its sender retracts it, or (for Sticky ones) the owner acknowledges it. Phase 2.
_Avoid_: alert, message, interrupt

**Sticky**:
A Notification flagged as must-see. It stays on screen until acknowledged rather than timing out. Acknowledgement hardware may not exist yet; the flag exists in the protocol from day one. Phase 2.
