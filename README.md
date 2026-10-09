# my-buddy

![Ping history: last 6 h at one point per minute, with the most-lost interval marked](docs/history-example.png)

MicroPython device that keeps time, pings 8.8.8.8, and shows the results on an st7789 display. Ping batches reach the Recorder over MQTT, where `receiver/history.sh` records them and serves `receiver/history.html`: round trip, jitter and loss over the last 15 min to 1 week, a crosshair across both charts, and a PNG export like the one above.

Layout: the repo root and `lib/` go on the Terminal; `receiver/` is the Recorder (runs on a VPS as a Docker image, `ghcr.io/minlaxz/buddy-receiver`); `tests/` are host self-checks plus `sender.sh`, a Sender for pushing a Message or LED by hand.

See `CONTEXT.md` and `docs/adr/` for the design.

## Recorder on a VPS

GitHub Actions builds `ghcr.io/minlaxz/buddy-receiver` (amd64 + arm64) on every push to `main` touching `receiver/`.

`docker-compose.yaml` runs the Recorder beside `cloudflared`. On the VPS, next to it, put a `.env`:

```sh
CLOUDFLARED_TUNNEL_TOKEN=...
MQTT_HOST=...
MQTT_USER=sender
MQTT_PASS=...
```

then `docker compose up -d`. In the tunnel, point the public hostname at `http://my-buddy-receiver:8000`. History lands in `./data/ping.jsonl`.

Bring over the History the Mac already recorded. Append, never overwrite: the recorder holds `ping.jsonl` open, and the page sorts rows by timestamp, so order does not matter. Safe before or after the stack starts.

```sh
scp ~/.local/share/buddy/ping.jsonl vps:/tmp/mac-ping.jsonl
ssh vps 'mkdir -p ~/my-buddy/data && cat /tmp/mac-ping.jsonl >> ~/my-buddy/data/ping.jsonl && rm /tmp/mac-ping.jsonl'
```

The page is read-only (no clear buttons); rows older than six months are dropped automatically.
