#!/usr/bin/env bash
# Sender: push a Message or LED to the Terminal through the Relay.
#
#   ./sender.sh message "hello"     ./sender.sh message ""     (clear)
#   ./sender.sh led '#00ff00'       ./sender.sh led off
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

CAFILE="$(cd "$(dirname "$0")" && pwd)/lib/isrg-root-x1.pem"

case "${1:-}" in
  message|led) topic="buddy/$1" ;;
  *) echo "usage: $0 message <text> | led <#rrggbb|off>" >&2; exit 2 ;;
esac

mosquitto_pub -h "$MQTT_HOST" -p 8883 --cafile "$CAFILE" \
  -u "$MQTT_USER" -P "$MQTT_PASS" -r -t "$topic" -m "${2-}"
