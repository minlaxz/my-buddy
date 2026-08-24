import socket
import time

import machine

from led import parse_color, DEFAULT_BRIGHTNESS


PORT = 80

# ponytail: whole request must fit here — a line, browser fetch headers
# (~800 bytes), a short form body. /message caps at 200 chars in the page;
# curl can send more and gets truncated.
REQUEST_BYTES = 2048

INDEX_FILE = "index.html"

# Chunk size when streaming the page out; keeps the heap calm on the device.
SEND_CHUNK = 512

# route() returns this as the body to mean "stream INDEX_FILE".
INDEX_FILE_MARK = object()


def unquote(s):
    """Decode application/x-www-form-urlencoded text."""

    s = s.replace("+", " ")
    parts = s.split("%")
    out = parts[0]

    for part in parts[1:]:
        try:
            out += chr(int(part[:2], 16)) + part[2:]
        except ValueError:
            out += "%" + part

    return out


def parse_form(s):
    """{key: value} from a query string or form body."""

    form = {}

    for pair in s.split("&"):
        if "=" in pair:
            k, v = pair.split("=", 1)
            form[unquote(k)] = unquote(v)

    return form


def parse_request(data):
    """(method, path, form) from raw request bytes; form merges query + body."""

    try:
        head, _, body = data.partition(b"\r\n\r\n")
        line = head.split(b"\r\n", 1)[0].decode()
        method, target, _version = line.split(" ", 2)
    except (ValueError, UnicodeError):
        return None, None, {}

    path, _, query = target.partition("?")

    form = parse_form(query)
    form.update(parse_form(body.decode()))

    return method, path, form


def content_length(data):
    for line in data.split(b"\r\n"):
        if line.lower().startswith(b"content-length:"):
            try:
                return int(line.split(b":", 1)[1])
            except ValueError:
                return 0
    return 0


def json_status(status):
    link = status.get("link")

    if link:
        ssid, ip, rssi = link
        link_json = '{{"ssid":"{}","ip":"{}","rssi":{}}}'.format(
            ssid, ip, "null" if rssi is None else rssi
        )
    else:
        link_json = "null"

    ping = status.get("ping")

    if ping:
        avg, loss, jitter = ping
        ping_json = '{{"avg_ms":{},"loss_pct":{},"jitter_ms":{}}}'.format(
            "null" if avg is None else avg,
            loss,
            "null" if jitter is None else jitter,
        )
    else:
        ping_json = "null"

    led = status.get("led")

    topics = ",".join('"{}"'.format(t) for t in status.get("topics", ()))

    return '{{"link":{},"ping":{},"uptime_s":{},"led":{},"relay":{},"topics":[{}]}}'.format(
        link_json,
        ping_json,
        status.get("uptime_s"),
        '"{}"'.format(led) if led else "null",
        "true" if status.get("relay") else "false",
        topics,
    )


class WebServer:
    """Tiny HTTP/1.0 server polled from the main loop. One request per poll."""

    def __init__(self, status, on_message, led):
        # status: callable returning {"link": (ssid, ip, rssi) | None, "uptime_s": int, "led": str | None}
        # on_message: callable(text) that puts a Message on the Page
        # led: led.Led
        self.status = status
        self.on_message = on_message
        self.led = led
        self.reboot_pending = False

        self.sock = socket.socket()
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("0.0.0.0", PORT))
        self.sock.listen(2)
        self.sock.setblocking(False)

    def poll(self):
        try:
            client, _addr = self.sock.accept()
        except OSError:
            return

        try:
            client.settimeout(0.5)
            data = client.recv(REQUEST_BYTES)

            # Body may trail the headers in a second segment (browser forms).
            head, sep, body = data.partition(b"\r\n\r\n")
            want = content_length(head) if sep else 0
            while len(body) < want and len(data) < REQUEST_BYTES:
                more = client.recv(REQUEST_BYTES - len(data))
                if not more:
                    break
                data += more
                body += more

            method, path, form = parse_request(data)
            code, ctype, body = self.route(method, path, form)

            if body is INDEX_FILE_MARK:
                client.send(
                    "HTTP/1.0 {}\r\nContent-Type: {}\r\n"
                    "Connection: close\r\n\r\n".format(code, ctype)
                )
                with open(INDEX_FILE, "rb") as f:
                    while True:
                        chunk = f.read(SEND_CHUNK)
                        if not chunk:
                            break
                        client.send(chunk)
            else:
                body = body.encode()
                client.send(
                    "HTTP/1.0 {}\r\nContent-Type: {}\r\nContent-Length: {}\r\n"
                    "Connection: close\r\n\r\n".format(code, ctype, len(body))
                )
                client.send(body)
        except OSError:
            pass
        finally:
            client.close()

        if self.reboot_pending:
            print("[Web] Reboot requested")
            # Let the FIN leave the radio before the chip goes away.
            time.sleep_ms(200)
            machine.reset()

    def route(self, method, path, form):
        if method == "GET" and path == "/":
            return "200 OK", "text/html", INDEX_FILE_MARK

        if method == "GET" and path == "/status":
            return "200 OK", "application/json", json_status(self.status())

        if method == "POST" and path == "/message":
            text = form.get("text", "")
            print("[Web] Message:", repr(text))
            self.on_message(text)
            return "200 OK", "text/plain", "Shown" if text else "Cleared"

        if method == "POST" and path == "/led":
            rgb = parse_color(form.get("color", "off"))
            print("[Web] LED:", form.get("color"), form.get("brightness"))

            if rgb is None:
                self.led.off()
                return "200 OK", "text/plain", "Off"

            try:
                brightness = int(form.get("brightness", DEFAULT_BRIGHTNESS))
            except ValueError:
                brightness = DEFAULT_BRIGHTNESS

            self.led.set(rgb, brightness)
            return "200 OK", "text/plain", self.led.color

        if method == "POST" and path == "/reboot":
            # Answer first, reset after the socket is closed.
            self.reboot_pending = True
            return "200 OK", "text/plain", "Rebooting"

        return "404 Not Found", "text/plain", "Not found"
