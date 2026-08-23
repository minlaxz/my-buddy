import socket
import time

import machine


PORT = 80

# ponytail: one read per request. Requests are a line and a few headers;
# nothing here accepts a body. Bump when a route needs POST data.
REQUEST_BYTES = 1024


def parse_request(data):
    """(method, path) from the raw request bytes, or (None, None)."""

    try:
        line = data.split(b"\r\n", 1)[0].decode()
        method, target, _version = line.split(" ", 2)
    except (ValueError, UnicodeError):
        return None, None

    return method, target.split("?", 1)[0]


def page(status):
    """The control page. `status` is the dict from the status callable."""

    link = status.get("link")

    if link:
        rows = "SSID: {}<br>IP: {}<br>RSSI: {} dBm".format(*link)
    else:
        rows = "Disconnected"

    return (
        "<!doctype html><title>Buddy</title>"
        "<h1>Buddy</h1><p>{}</p><p>Uptime: {} s</p>"
        "<form method=post action=/reboot><button>Reboot</button></form>"
    ).format(rows, status.get("uptime_s"))


def json_status(status):
    link = status.get("link")

    if link:
        ssid, ip, rssi = link
        link_json = '{{"ssid":"{}","ip":"{}","rssi":{}}}'.format(
            ssid, ip, "null" if rssi is None else rssi
        )
    else:
        link_json = "null"

    return '{{"link":{},"uptime_s":{}}}'.format(link_json, status.get("uptime_s"))


class WebServer:
    """Tiny HTTP/1.0 server polled from the main loop. One request per poll."""

    def __init__(self, status):
        # status: callable returning {"link": (ssid, ip, rssi) | None, "uptime_s": int}
        self.status = status
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
            method, path = parse_request(client.recv(REQUEST_BYTES))
            code, ctype, body = self.route(method, path)
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

    def route(self, method, path):
        if method == "GET" and path == "/":
            return "200 OK", "text/html", page(self.status())

        if method == "GET" and path == "/status":
            return "200 OK", "application/json", json_status(self.status())

        if method == "POST" and path == "/reboot":
            # Answer first, reset after the socket is closed.
            self.reboot_pending = True
            return "200 OK", "text/plain", "Rebooting"

        return "404 Not Found", "text/plain", "Not found"
