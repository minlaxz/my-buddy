"""Serve the History page and clear ranges of its data. Started by history.sh.

GET  /            history.html (symlinked as index.html) and ping.jsonl
POST /clear?hours=N   drop rows newer than N hours; hours=0 drops everything

Rows older than MAX_AGE (6 months) are dropped at start and once a day.
"""

import json
import os
import sys
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse


MAX_AGE = 183 * 86400  # 6 months
_lock = threading.Lock()  # the daily prune and a clear button must not rewrite at once


def rewrite(path, keep):
    """Rewrite the JSONL in place with only the rows whose unix-second timestamp passes `keep`.
    In place, not rename: the recorder's O_APPEND fd must keep pointing at it.
    ponytail: a chunk appended between the read and the truncate is lost; one
    chunk every 3 s, acceptable for a button and a daily sweep."""

    kept = 0

    with _lock, open(path, "r+") as f:
        lines = f.readlines()
        f.seek(0)

        for line in lines:
            try:
                obj = json.loads(line)
                rows = [r for r in obj["payload"] if keep(r[0])]
            except (ValueError, KeyError, TypeError):
                continue
            if rows:
                obj["payload"] = rows
                f.write(json.dumps(obj, separators=(",", ":")) + "\n")
                kept += len(rows)

        f.truncate()

    return kept


def clear(path, hours, now=None):
    """Drop rows newer than `hours` ago (0 = everything)."""
    since = (now or time.time()) - hours * 3600
    return rewrite(path, (lambda t: t < since) if hours else (lambda t: False))


def prune(path, now=None):
    """Drop rows older than MAX_AGE."""
    cutoff = (now or time.time()) - MAX_AGE
    return rewrite(path, lambda t: t >= cutoff)


def serve(data_dir, port):
    path = os.path.join(data_dir, "ping.jsonl")

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=data_dir, **k)

        def do_POST(self):
            url = urlparse(self.path)
            if url.path != "/clear":
                return self.send_error(404)

            hours = float(parse_qs(url.query).get("hours", ["0"])[0])
            kept = clear(path, hours) if os.path.exists(path) else 0
            body = "{} batches kept".format(kept).encode()

            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    def daily():
        while True:
            if os.path.exists(path):
                prune(path)
            time.sleep(86400)

    threading.Thread(target=daily, daemon=True).start()
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    if sys.argv[1:] == ["--check"]:  # host self-check: python3 history_server.py --check
        import tempfile

        p = tempfile.mktemp()
        line = lambda ts: json.dumps({"tst": "x", "payload": [[t, 1, 0, 1] for t in ts]}) + "\n"
        with open(p, "w") as f:
            f.write(line([100, 200]) + "garbage\n" + line([3000, 4000]))

        assert clear(p, 1, now=7100) == 3  # since 3500: 100, 200, 3000 stay, 4000 goes, garbage goes
        assert [json.loads(l)["payload"] for l in open(p)] == [[[100, 1, 0, 1], [200, 1, 0, 1]], [[3000, 1, 0, 1]]]
        assert prune(p, now=200 + MAX_AGE) == 2  # cutoff 200: 100 goes, 200 and 3000 stay
        assert [json.loads(l)["payload"] for l in open(p)] == [[[200, 1, 0, 1]], [[3000, 1, 0, 1]]]
        assert clear(p, 0) == 0 and open(p).read() == ""
        os.remove(p)
        print("ok")
    else:
        serve(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 8000)
