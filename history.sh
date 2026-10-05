#!/usr/bin/env bash
# History: record Ping batches from the Terminal and serve the graph.
#
#   ./history.sh            record to ~/.local/share/buddy/ping.jsonl and
#                           serve http://localhost:8000 until Ctrl-C
#
# Credentials: the same ~/.config/buddy/sender.env as sender.sh.
#
# While this runs, retained bud/history = on tells the Terminal the Mac is
# listening; it then drains every batch it has held (RAM + flash) in chunks
# on bud/ping, and keeps sending each new batch as it lands. Ctrl-C or a
# crash flips the flag off (trap / MQTT will) and the Terminal holds again.
#
# One JSON line per chunk, rows timestamped by the Terminal (unix s):
#   {"tst":"...","topic":"bud/ping",...,"payload":[[1759600000,12,0,3],...]}
#
# The page's "clear" buttons POST /clear to history_server.py, which rewrites
# the file in place without the chosen range.

set -euo pipefail

: "${BUDDY_SENDER_ENV:=$HOME/.config/buddy/sender.env}"
[ -f "$BUDDY_SENDER_ENV" ] && . "$BUDDY_SENDER_ENV"
: "${MQTT_HOST:?set MQTT_HOST in $BUDDY_SENDER_ENV}"
: "${MQTT_USER:?set MQTT_USER in $BUDDY_SENDER_ENV}"
: "${MQTT_PASS:?set MQTT_PASS in $BUDDY_SENDER_ENV}"

HERE="$(cd "$(dirname "$0")" && pwd)"
DATA="${BUDDY_HISTORY_DIR:-$HOME/.local/share/buddy}"
mkdir -p "$DATA"
ln -sf "$HERE/history.html" "$DATA/index.html"

MQ=(-h "$MQTT_HOST" -p 8883 --cafile "$HERE/lib/isrg-root-x1.pem" -u "$MQTT_USER" -P "$MQTT_PASS")

# Fixed client id: a second copy of this script kicks the first off the broker.
mosquitto_sub "${MQ[@]}" -i buddy-history -t bud/ping -F %J \
  --will-topic bud/history --will-payload off --will-retain >>"$DATA/ping.jsonl" &
SUB=$!
python3 "$HERE/history_server.py" "$DATA" 8000 &
SRV=$!
trap 'kill $SUB $SRV 2>/dev/null; mosquitto_pub "${MQ[@]}" -r -t bud/history -m off' EXIT

sleep 0.5  # subscribed before the flag goes up, so the first chunk is not missed
mosquitto_pub "${MQ[@]}" -r -t bud/history -m on

echo "recording bud/ping -> $DATA/ping.jsonl"
echo "graph: http://localhost:8000"
wait $SRV
