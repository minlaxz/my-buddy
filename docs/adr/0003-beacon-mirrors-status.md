# The Beacon mirrors Status, and goes dark rather than lie

The onboard RGB LED shows Claude Code's Status as colour alone. Four decisions in it look arbitrary and are not.

**It is driven by the `state` message already on the wire.** `buddy.sh` publishes `state: working|idle|needs you|sleeping` to the `claude-code` topic, and the Terminal already reads it for the header. The Beacon reacts to the same message in `main.py`'s `set_state()`. No new ntfy title, no new hook, no second protocol to keep aligned — a Sender that can set the Status cannot set the Beacon separately, by construction.

**The pin is 48, not 38.** GPIO 38 is the number printed in much of the ESP32-S3 material and it is wrong for this board. Writing a NeoPixel frame to the wrong pin raises nothing — `neopixel` bit-bangs happily into an unconnected pin and the LED stays dark, which is indistinguishable from a dead LED, a wrong colour order, or a brightness of zero. Confirmed by writing red to 48 and seeing it.

**Colours duplicate `display.STATE_COLORS` instead of importing them.** `display.py` holds `st7789` 16-bit RGB565 constants; the Beacon needs 8-bit-per-channel tuples for a WS2812. Converting between them at runtime, to save four lines of table, would couple the LED to the TFT driver's colour encoding for nothing. The rule is that the two tables carry the same hues — enforced by review, not by code.

**Brightness is one constant at 5%.** Full scale is a 40 mA point source an arm's length from the owner's eyes. 13/255 was checked on the actual desk and reads across the room. It is a scale factor applied to every colour rather than four pre-dimmed tuples, so tuning for a different LED is one number.

**A dead stream blanks it after 15 seconds.** The stream reconnects routinely with a 5 s backoff, so `sock is None` alone is not a fault. But if the link truly dies while Claude is working, a Beacon left yellow keeps asserting a fact the Terminal stopped being able to observe — and unlike the header, which sits beside a visibly stale Wi-Fi panel, the Beacon carries no context to undercut it. Dark is the honest reading.

## Consequences

- A new state string added to `buddy.sh` shows white on the Beacon and white in the header until both tables learn it. That is deliberate: an unknown state is visible rather than silently absent.
- `sleeping` and "no Status at all" are the same colour — off. The Terminal cannot distinguish "session ended" from "never started" on the LED alone; the header still can.
- The 15 s stale rule means a link that flaps every 10 s never blanks the Beacon, and one down for 20 s blanks it even if Claude is genuinely still working. Both are correct under "colour must not outlive the evidence for it".
- The Beacon writes on state change only, never per tick, so it costs the main loop nothing between Status messages.
