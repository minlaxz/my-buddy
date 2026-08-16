# Hermes

A personal companion system in two parts: a physical ESP32-S3 + 240x240 TFT unit on the owner's desk, and (phase 2) a personal AI agent on a VPS that uses the desk unit as its voice. Today the desk unit monitors the network and relays Notifications and Status from authorized senders — Claude Code is the first.

## Language

**Hermes**:
The whole companion system — desk Terminal plus (eventually) the Agent.
_Avoid_: my-buddy (repo name only)

**Terminal**:
The physical ESP32-S3 + TFT unit on the desk, and the MicroPython firmware it runs. This repo is the Terminal's code.
_Avoid_: the board, the device, ESP32 (that's the chip, not the role)

**Hermes Agent**:
The owner's personal AI agent, living on a VPS. It does the thinking; when it wants to say something (e.g. a greeting), it acts as a Sender and pushes a Notification to the Terminal. Phase 2 — does not exist in this repo yet, though the channel it will use does.
_Avoid_: server, backend

**Capability**:
A distinct thing the Terminal can do for its owner. Phase 1 has one: network monitoring. Notifications and Status are not Capabilities — they cut across whatever Page is showing.

**Page**:
A full-screen view owned by one capability. With one capability there is one Page; when several exist they rotate on a timer.
_Avoid_: screen, dashboard, view

**Sender**:
Anything outside the Terminal authorized to push a Notification or Status to it. Today: Claude Code, via its hooks. Eventually: the Hermes Agent. Senders share one subscription, so a new one costs the Terminal no new connection.
_Avoid_: client, publisher

**Notification**:
A message pushed to the Terminal by a Sender. Takes over the screen, interrupting the current Page, until it times out, its sender retracts it, or (for Sticky ones) the owner acknowledges it. Retraction is not built; today every Notification times out.
_Avoid_: alert, message, interrupt

**Status**:
A persistent one-line indicator of a Sender's current state, drawn in the header beside the Hermes label. Unlike a Notification it never interrupts the Page and never times out — it stays until the Sender replaces it, and survives a Notification passing over it. Colour carries the meaning; the text names the state.
_Avoid_: status bar, banner, indicator

**Beacon**:
The onboard RGB LED, showing the current Status as colour alone — the same states and the same hues as the header, with no text. It is a second rendering of Status, not a thing of its own: nothing can set the Beacon that could not set the Status. Visible from across the room and while the Terminal faces away, so it answers "is Claude working?" without reading the Page. Dark means the Terminal has no Status to show — at boot, after a Sender sleeps, or when the stream has been down long enough that the last state can no longer be trusted.
_Avoid_: LED, light, RGB (those name the part, not the role)

**Sticky**:
A Notification flagged as must-see. It stays on screen until acknowledged rather than timing out. Acknowledgement hardware may not exist yet; the flag exists in the protocol from day one. Phase 2 — a Status is not a Sticky, since nothing acknowledges it.
