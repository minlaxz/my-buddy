# The Recorder runs always-on on a VPS, shipped as a Docker image

Status: accepted, 2026-10-09. Amends ADR-0007, which put the recorder on the owner's Mac.

The Mac sleeps, so under ADR-0007 the Terminal held batches for hours and the graph was only as fresh as the last time the Mac was awake. Moving the recorder to an always-on VPS turns holding into the exception: the retained `bud/history` flag stays `on`, and the Terminal holds only while it cannot reach the Relay (Wi-Fi down, WAN down, broker down). The firmware rule is unchanged; only who raises the flag moved.

**Same scripts, in a container.** `receiver/history.sh` and `history_server.py` move from `mac/`; the CA file and listen address became env vars so the image can bind `0.0.0.0` and the Mac can still run it locally on `127.0.0.1`. The image is Alpine with `bash`, `python3` and `mosquitto-clients`, built by `.github/workflows/receiver.yml` and pushed to GHCR for amd64 and arm64. Data lives in `/data`, bind-mounted from `./data` beside `docker-compose.yaml` so a JSONL recorded on the Mac can be appended to it. bash is PID 1, so `docker stop` reaches its TERM trap, which kills `mosquitto_sub` with -9 and the broker fires the will (`off`).

**Read-only page, exposure is the tunnel's job.** The clear buttons and `POST /clear` are gone: on a public hostname they were a delete button for anyone. Only the six-month prune removes rows now. The container publishes plain HTTP; `docker-compose.yaml` runs it beside `cloudflared`, which reaches it over the compose network at `http://my-buddy-receiver:8000`; no port is published on the host.

**One recorder at a time.** The fixed client id `buddy-history` means running `history.sh` on the Mac while the VPS one is up makes them kick each other off every 5 s. Stop one.

`mac/` is gone; the Sender moved to `tests/sender.sh`. The status key on the Control Page and `GET /status` is `recorder`, no longer `mac`.
