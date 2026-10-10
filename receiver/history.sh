#!/usr/bin/env bash
# History: record Ping batches from the Terminal and serve the graph.
#
#   receiver/history.sh    record to ~/.local/share/buddy/ping.db and
#                           serve http://localhost:8000 until Ctrl-C
#
# Credentials: MQTT_HOST/USER/PASS from the environment, or the same
# ~/.config/buddy/sender.env as tests/sender.sh. In the Docker image the data
# dir is /data and the server listens on 0.0.0.0 (see Dockerfile).
#
# One recorder at a time: the fixed client id means a second copy (the Mac
# while the VPS runs) kicks the first off, and they take turns every 5 s.
#
# While this runs, retained bud/history = on tells the Terminal the Mac is
# listening; it then drains every batch it has held (RAM + flash) in chunks
# on bud/ping, and keeps sending each new batch as it lands. The flag is the
# recorder's MQTT will: any way the recorder's connection ends (Ctrl-C, crash,
# broker drop) flips it off and the Terminal holds again.
#
# mosquitto_sub does not reconnect: when the broker drops it ("Error: The
# connection was lost") this script starts a new one and raises the flag again.
#
# One JSON line per chunk, rows timestamped by the Terminal (unix s), piped
# into ingest.py, which stores each row in ping.db (SQLite) once:
#   {"tst":"...","topic":"bud/ping",...,"payload":[[1759600000,12,0,3],...]}
#
# history_server.py drops rows older than 6 months at start and once a day.
# An old JSONL (e.g. from the Mac) goes in with ingest.py at any time, even
# while this runs: python3 ingest.py ping.db old.jsonl

set -euo pipefail

: "${BUDDY_SENDER_ENV:=$HOME/.config/buddy/sender.env}"
[ -f "$BUDDY_SENDER_ENV" ] && . "$BUDDY_SENDER_ENV"
: "${MQTT_HOST:?set MQTT_HOST in $BUDDY_SENDER_ENV}"
: "${MQTT_USER:?set MQTT_USER in $BUDDY_SENDER_ENV}"
: "${MQTT_PASS:?set MQTT_PASS in $BUDDY_SENDER_ENV}"

HERE="$(cd "$(dirname "$0")" && pwd)"
DATA="${BUDDY_HISTORY_DIR:-$HOME/.local/share/buddy}"
PORT="${BUDDY_HISTORY_PORT:-8000}"
BIND="${BUDDY_HISTORY_BIND:-127.0.0.1}"
CAFILE="${MQTT_CAFILE:-$HERE/../lib/isrg-root-x1.pem}"
mkdir -p "$DATA"
ln -sf "$HERE/history.html" "$DATA/index.html"

MQ=(-h "$MQTT_HOST" -p 8883 --cafile "$CAFILE" -u "$MQTT_USER" -P "$MQTT_PASS")

# Fixed client id: a second copy of this script kicks the first off the broker.
SUB_ARGS=(-i buddy-history -t bud/ping -F %J --will-topic bud/history --will-payload off --will-retain)

python3 "$HERE/history_server.py" "$DATA" "$PORT" "$BIND" &
SRV=$!
SUB=
# Shutdown relies on the will: a dead socket fires it, a DISCONNECT does not.
# mosquitto_sub installs its own SIGINT/SIGTERM handler that DISCONNECTs, so it
# runs in its own process group (Ctrl-C never reaches it) and is killed -9.
# `|| true`: under set -e a kill of an already-dead pid would abort the trap.
trap '{ kill -9 $SUB; kill $SRV; } 2>/dev/null || true' EXIT
trap 'exit 130' INT TERM HUP

echo "recording bud/ping -> $DATA/ping.db"
echo "graph: http://$BIND:$PORT"

while kill -0 $SRV 2>/dev/null; do
  # Process substitution, not a pipe: $! stays mosquitto_sub's pid for the
  # kill -9, and ingest.py ends on its own at EOF when mosquitto_sub dies.
  python3 -c 'import os, sys; os.setpgrp(); os.execvp(sys.argv[1], sys.argv[1:])' \
    mosquitto_sub "${MQ[@]}" "${SUB_ARGS[@]}" > >(python3 "$HERE/ingest.py" "$DATA/ping.db") &
  SUB=$!
  sleep 0.5  # subscribed before the flag goes up, so the first chunk is not missed
  mosquitto_pub "${MQ[@]}" -r -t bud/history -m on || true
  wait $SUB || true
  echo "$(date '+%F %T') recorder dropped, reconnecting in 5 s" >&2
  sleep 5
done
wait $SRV  # the server is gone: exit with its status
