#!/usr/bin/env bash
# Sender: push a Message or LED to the Terminal through the Relay.
#
#   mac/sender.sh message "hello"     mac/sender.sh message ""     (clear)
#   mac/sender.sh led '#00ff00'       mac/sender.sh led off
#
# Topics: message -> bud/msg, led -> bud/led.
#
# Credentials never live in this repo. Put the publish-only pair in
# ~/.config/buddy/sender.env (or point BUDDY_SENDER_ENV elsewhere):
#
#   MQTT_HOST=xxxxxxxx.s1.eu.hivemq.cloud
#   MQTT_USER=sender
#   MQTT_PASS=...
#
# Published retained: the Terminal picks the last value up whenever it
# (re)connects to the Relay, even after a reboot.

set -euo pipefail

: "${BUDDY_SENDER_ENV:=$HOME/.config/buddy/sender.env}"
[ -f "$BUDDY_SENDER_ENV" ] && . "$BUDDY_SENDER_ENV"
: "${MQTT_HOST:?set MQTT_HOST in $BUDDY_SENDER_ENV}"
: "${MQTT_USER:?set MQTT_USER in $BUDDY_SENDER_ENV}"
: "${MQTT_PASS:?set MQTT_PASS in $BUDDY_SENDER_ENV}"

CAFILE="$(cd "$(dirname "$0")/.." && pwd)/lib/isrg-root-x1.pem"

case "${1:-}" in
  message) topic="bud/msg" ;;
  led)     topic="bud/led" ;;
  *) echo "usage: $0 message <text> | led <#rrggbb|off>" >&2; exit 2 ;;
esac

# Feedback loop: the Terminal publishes a non-retained Receipt on <topic>/ack
# right after it renders. Subscribe BEFORE publishing (a fired Receipt is not
# retained — miss the window and it is gone), then wait up to 5 s for it.
tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT

mosquitto_sub -h "$MQTT_HOST" -p 8883 --cafile "$CAFILE" \
  -u "$MQTT_USER" -P "$MQTT_PASS" -t "$topic/ack" -C 1 -W 5 >"$tmp" 2>/dev/null &
sub_pid=$!

sleep 0.3  # ponytail: grace for the sub to connect before we publish; swap for a readiness probe only if it ever misses.

mosquitto_pub -h "$MQTT_HOST" -p 8883 --cafile "$CAFILE" \
  -u "$MQTT_USER" -P "$MQTT_PASS" -r -t "$topic" -m "${2-}"

# Gate on the sub's exit: 0 = Receipt received, 27 = timed out. NOT on file
# size — a "clear" acks with an empty payload, which writes zero bytes.
if wait "$sub_pid"; then
  rendered="$(cat "$tmp")"
  printf 'Terminal rendered: %s\n' "${rendered:-(cleared)}"
else
  echo "no ack — Terminal offline or not rendering" >&2
  exit 1
fi
