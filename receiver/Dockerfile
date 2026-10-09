# History recorder + graph server. Build from the repo root:
#   docker build -f receiver/Dockerfile -t buddy-receiver .
FROM alpine:3.20

RUN apk add --no-cache bash python3 mosquitto-clients

COPY lib/isrg-root-x1.pem /app/lib/isrg-root-x1.pem
COPY receiver/ /app/receiver/

ENV BUDDY_HISTORY_DIR=/data \
    BUDDY_HISTORY_PORT=8000 \
    BUDDY_HISTORY_BIND=0.0.0.0 \
    PYTHONUNBUFFERED=1
VOLUME /data
EXPOSE 8000

# bash is PID 1: its TERM trap kill -9s mosquitto_sub so the broker fires the
# will (bud/history = off) on `docker stop`.
ENTRYPOINT ["/app/receiver/history.sh"]
