---
status: accepted
---

# The Relay is MQTT on HiveMQ Cloud, beside the Control Page, as an experiment

ADR-0005 rejected MQTT because there was no broker and no need. On 2026-08-24 a HiveMQ Cloud broker existed and the owner wanted to see what it enables — that is the whole reason. Nothing on the desk needs the Relay today; the Control Page over LAN does the same two things. This ADR records the experiment so the next reader does not mistake it for a requirement. **If nothing uses the Relay by 2026-09-24, delete `relay.py`, its `secrets.py` keys and this ADR's status becomes `deprecated`.**

## Decisions

**Beside, not instead.** The Control Page stays and keeps working with no internet. Both channels call the same two functions (`display.show_message`, `led.set`/`led.off`). ADR-0005 stands for the Control Page.

**Two inbound topics, retained, plain text.** `bud/msg` carries the Message text (empty clears); `bud/led` carries `#rrggbb` or `off`, parsed by the same `parse_color` the Control Page uses, at default brightness. Retained is the one thing HTTP cannot do: a Terminal that reboots or was away picks up the last Message and LED on connect. No JSON, so a human can type payloads by hand.

**One outbound topic: the Receipt.** The Terminal publishes a non-retained Receipt on `<topic>/ack` (`bud/msg/ack`, `bud/led/ack`) right after it renders, echoing what it rendered (the stripped Message text; the LED colour `#rrggbb` or `off`). The Sender subscribes to the ack topic *before* it publishes, then waits up to 5 s: a Receipt in the window is the feedback loop that `sender.sh message "x"` succeeded on the glass, not just at the broker. Correlation is by timing, not payload — the Receipt is non-retained and the Sender is already listening, so the next ack is ours; the payload is printed for the human, never matched (a strict match would force `sender.sh` to re-implement the device's strip/lowercasing and produce false negatives). Still no `online` / last-will; retained inbound already covers "the Terminal was away."

**Two credentials on the broker, both publish and subscribe.** `terminal` subscribes to `bud/msg`,`bud/led` and publishes only `bud/+/ack`; `sender` publishes `bud/msg`,`bud/led` and subscribes `bud/+/ack`. The Terminal's credentials and the broker host live in `secrets.py` (gitignored) next to `WIFI_NETWORKS`; the Sender's live on the Mac, never in this repo. A dumped flash can publish only Receipts, never Messages or LED.

**TLS with the CA pinned when the firmware allows it.** HiveMQ Cloud is TLS-only on 8883 with Let's Encrypt certificates. MicroPython ≥ 1.23 can verify against ISRG Root X1 (`lib/isrg-root-x1.pem`, ~1.5 KB, `SSLContext.load_verify_locations`). Older firmware falls back to `CERT_NONE` with a `# ponytail:` comment naming the upgrade; the harm ceiling of a spoofed Relay is wrong text on a desk toy.

**Polled from the main loop, same cadence as Wi-Fi.** Connect only while the Wi-Fi Link is up; the TLS handshake blocks 2–5 s and the Heartbeat freezes for it, exactly as it does for a Wi-Fi join. Retry every `RECONNECT_MS` (30 s), `check_msg()` every tick, `ping()` every 30 s with a 60 s keepalive. Any `OSError` on the socket drops it and returns to the retry path.

## Consequences

- **The Relay's last word wins on reconnect.** Sender sets "A"; owner sets "B" on the Control Page; Wi-Fi blips; the Relay replays retained "A" on resubscribe and "B" is gone. Accepted and written into the glossary. The fix, if it ever bites, is for the Control Page to publish too — which makes the Terminal a Sender and needs a third credential.
- Relay state (up/down) shows bottom-left on the Page and in the Control Page `system` panel; the Page's Pub line now names the Receipt topics (`bud/+/ack`). Nothing more — no host, no last-message time — until asked for.
- **Timing-correlated Receipts can false-positive.** Two Senders publishing to the same topic within one 5 s window: each sees the other's Receipt and both report success. One desk, effectively one Sender — accepted, not engineered around.
- **The Receipt is the first real use of the Relay.** It weakens the delete-by clause above: `sender.sh` now depends on the Relay round-trip, so "nothing uses the Relay" is no longer true.
- A dead broker or expired credential costs one blocked handshake attempt every 30 s, each stalling the Heartbeat a few seconds. Visible, not harmful.
- `mpremote cp` still kills `main.py`; the Relay is gone with it until reset, like the Control Page.
