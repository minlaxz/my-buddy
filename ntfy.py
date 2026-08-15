import json
import time

try:
    import socket
except ImportError:
    import usocket as socket

try:
    import ssl
except ImportError:
    import ussl as ssl


# ponytail: raw socket, not urequests. urequests has no non-blocking read, and a
# blocking stream read would stall the main loop's animation/countdown.
# HTTP/1.0 on purpose: forbids chunked transfer-encoding, so the body is plain
# newline-delimited JSON with no chunk-size lines to strip.
class NtfyStream:
    """Non-blocking reader for a ntfy `/<topic>/json` stream."""

    def __init__(
        self,
        host,
        topic,
        port=443,
        use_ssl=True,
        idle_timeout_ms=90_000,
        retry_ms=5_000,
    ):
        self.host = host
        self.topic = topic
        self.port = port
        self.use_ssl = use_ssl
        # ntfy sends a keepalive event every ~45s; longer silence means dead link.
        self.idle_timeout_ms = idle_timeout_ms
        self.retry_ms = retry_ms
        self.sock = None
        self.buf = b""
        self.headers_done = False
        self.last_rx = 0
        self.retry_at = 0

    def close(self):
        if self.sock is not None:
            try:
                self.sock.close()
            except Exception:
                pass
        self.sock = None
        self.buf = b""
        self.headers_done = False

    def connect(self):
        self.close()

        addr = socket.getaddrinfo(self.host, self.port)[0][-1]

        sock = socket.socket()
        sock.settimeout(10)
        sock.connect(addr)

        if self.use_ssl:
            sock = ssl.wrap_socket(sock, server_hostname=self.host)

        request = (
            "GET /{}/json HTTP/1.0\r\n"
            "Host: {}\r\n"
            "Accept: application/x-ndjson\r\n"
            "\r\n"
        ).format(self.topic, self.host)

        sock.write(request.encode())
        sock.setblocking(False)

        self.sock = sock
        self.last_rx = time.ticks_ms()

    def poll(self):
        """Return the newest message text, or None. Never blocks."""

        if self.sock is None:
            # ponytail: connect() blocks for the DNS+TCP+TLS handshake, so the
            # backoff also caps how often the main loop can stall on a dead link.
            if time.ticks_diff(time.ticks_ms(), self.retry_at) < 0:
                return None

            try:
                self.connect()
            except Exception as e:
                print("[ntfy] connect failed:", repr(e))
                self.close()
                self.retry_at = time.ticks_add(time.ticks_ms(), self.retry_ms)

            return None

        try:
            data = self.sock.read(512)
        except OSError:
            # ponytail: EAGAIN and mbedtls WANT_READ look the same here. Treat any
            # OSError as "no data"; idle_timeout_ms reaps a genuinely dead socket.
            data = None
        except Exception as e:
            print("[ntfy] read failed:", repr(e))
            self.close()
            return None

        now = time.ticks_ms()

        if data:
            self.last_rx = now
            self.buf += data
        elif data == b"":
            # Server closed the stream.
            self.close()
            self.retry_at = time.ticks_add(now, self.retry_ms)
            return None
        elif time.ticks_diff(now, self.last_rx) > self.idle_timeout_ms:
            print("[ntfy] idle timeout, reconnecting")
            self.close()
            self.retry_at = time.ticks_add(now, self.retry_ms)
            return None

        if not self.headers_done:
            i = self.buf.find(b"\r\n\r\n")
            if i < 0:
                return None

            status = self.buf[: self.buf.find(b"\r\n")]

            if b" 200 " not in status:
                # Auth failures answer 401/403 and would otherwise look like silence.
                print("[ntfy] bad status:", status)
                self.close()
                self.retry_at = time.ticks_add(now, self.retry_ms)
                return None

            self.headers_done = True
            self.buf = self.buf[i + 4 :]

        message = None

        while True:
            i = self.buf.find(b"\n")
            if i < 0:
                break

            line = self.buf[:i].strip()
            self.buf = self.buf[i + 1 :]

            if not line:
                continue

            try:
                event = json.loads(line)
            except Exception:
                print("[ntfy] bad JSON:", line)
                continue

            if event.get("event") == "message":
                message = event.get("message", "")

        # Guard against a runaway line with no newline eating all the RAM.
        if len(self.buf) > 4096:
            self.buf = b""

        return message
