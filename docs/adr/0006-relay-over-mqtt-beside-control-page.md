---
status: accepted
---

# The Relay is MQTT on HiveMQ Cloud, beside the Control Page, as an experiment

ADR-0005 rejected MQTT because there was no broker and no need. On 2026-08-24 a HiveMQ Cloud broker existed and the owner wanted to see what it enables — that is the whole reason. Nothing on the desk needs the Relay today; the Control Page over LAN does the same two things. This ADR records the experiment so the next reader does not mistake it for a requirement. **If nothing uses the Relay by 2026-09-24, delete `relay.py`, its `secrets.py` keys and this ADR's status becomes `deprecated`.**

## Decisions

**Beside, not instead.** The Control Page stays and keeps working with no internet. Both channels call the same two functions (`display.show_message`, `led.set`/`led.off`). ADR-0005 stands for the Control Page.

**Two inbound topics, retained, plain text.** `buddy/message` carries the Message text (empty clears); `buddy/led` carries `#rrggbb` or `off`, parsed by the same `parse_color` the Control Page uses, at default brightness. Retained is the one thing HTTP cannot do: a Terminal that reboots or was away picks up the last Message and LED on connect. No JSON, so a human can type payloads by hand.

**No outbound topics.** No `online` / last-will. Retained inbound already covers "the Terminal was away"; add `online` when something reads it.

**Two credentials on the broker.** `terminal` may only subscribe to `buddy/#`; `sender` may only publish to it. The Terminal's credentials and the broker host live in `secrets.py` (gitignored) next to `WIFI_NETWORKS`; the Sender's live on the Mac, never in this repo. A dumped flash cannot be used to publish.

**TLS with the CA pinned when the firmware allows it.** HiveMQ Cloud is TLS-only on 8883 with Let's Encrypt certificates. MicroPython ≥ 1.23 can verify against ISRG Root X1 (`lib/isrg-root-x1.pem`, ~1.5 KB, `SSLContext.load_verify_locations`). Older firmware falls back to `CERT_NONE` with a `# ponytail:` comment naming the upgrade; the harm ceiling of a spoofed Relay is wrong text on a desk toy.

**Polled from the main loop, same cadence as Wi-Fi.** Connect only while the Wi-Fi Link is up; the TLS handshake blocks 2–5 s and the Heartbeat freezes for it, exactly as it does for a Wi-Fi join. Retry every `RECONNECT_MS` (30 s), `check_msg()` every tick, `ping()` every 30 s with a 60 s keepalive. Any `OSError` on the socket drops it and returns to the retry path.

## Consequences

- **The Relay's last word wins on reconnect.** Sender sets "A"; owner sets "B" on the Control Page; Wi-Fi blips; the Relay replays retained "A" on resubscribe and "B" is gone. Accepted and written into the glossary. The fix, if it ever bites, is for the Control Page to publish too — which makes the Terminal a Sender and needs a third credential.
- Relay state (up/down) shows bottom-left on the Page and in the Control Page `system` panel. Nothing more — no host, no last-message time — until asked for.
- A dead broker or expired credential costs one blocked handshake attempt every 30 s, each stalling the Heartbeat a few seconds. Visible, not harmful.
- `mpremote cp` still kills `main.py`; the Relay is gone with it until reset, like the Control Page.
