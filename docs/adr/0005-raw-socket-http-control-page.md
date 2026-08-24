# The Control Page is a raw-socket HTTP/1.0 server polled from the main loop

`web.py` is ~150 lines on `socket` and nothing else. Three choices in it look naive and are deliberate:

**Polled, not asyncio.** The main loop is a `while True` that ticks the Heartbeat every 100 ms and reads the Wi-Fi Link every 5 s. Microdot or a hand-rolled `asyncio` server would mean rewriting that loop as tasks for the sake of one page with four routes. The listen socket is non-blocking; `poll()` accepts at most one client per tick, answers it, closes it. Concurrency is the tick rate, which is plenty for one owner's browser. Revisit when routes pass ~6 or something needs WebSockets.

**HTTP/1.0, `Connection: close`, one `recv` per request.** No keep-alive, no chunked encoding, no streaming bodies. The whole request must fit `REQUEST_BYTES` (2 KB); the page caps Message at 200 chars so browser fetch headers plus body fit. Responses carry `Content-Length` so a client does not wait on the FIN — `POST /reboot` resets the chip 200 ms after close, and without the header the client hung.

**Static page + JSON, not templates.** `index.html` is served verbatim from flash in 512-byte chunks; its JavaScript polls `GET /status` and POSTs form-encoded bodies. Keeps Python free of HTML strings and keeps the page editable by a browser person without touching MicroPython.

Rejected: MQTT (needs a broker; the owner is on the same LAN, nothing is queued while the Terminal is away — revisited as an experiment in ADR-0006 once a broker existed; the Control Page stays), WebREPL (a shell, not a product), the old ntfy push channel (removed with the test-phase features).

## Consequences

- **No authentication.** Anyone on the LAN can set the Message, the LED, or reboot. Acceptable for a home network; add a shared token header before exposing the port anywhere else.
- A single slow client blocks the loop for up to the socket timeout (0.5 s) — the Heartbeat stutters, nothing breaks.
- `mpremote cp` interrupts `main.py`; the server is gone until a reset. Upload, then reset.
