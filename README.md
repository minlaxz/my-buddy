# my-buddy

![Ping history: last 6 h at one point per minute, with the most-lost interval marked](docs/history-example.png)

MicroPython device that keeps time, pings 8.8.8.8, and shows the results on an st7789 display. Ping batches reach a Mac over MQTT, where `history_server.py` serves `history.html`: round trip, jitter and loss over the last 15 min to 1 week, a crosshair across both charts, and a PNG export like the one above.

See `CONTEXT.md` and `docs/adr/` for the design.
