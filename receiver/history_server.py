"""Serve the History page and its data, read-only. Started by history.sh.

GET  /            history.html (symlinked as index.html) and ping.jsonl

Rows older than MAX_AGE (6 months) are dropped at start and once a day.
"""

import json
import os
import sys
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer


MAX_AGE = 183 * 86400  # 6 months


def rewrite(path, keep):
    """Rewrite the JSONL in place with only the rows whose unix-second timestamp passes `keep`.
    In place, not rename: the recorder's O_APPEND fd must keep pointing at it.
    ponytail: a chunk appended between the read and the truncate is lost; one
    chunk every 3 s, acceptable for a daily sweep."""

    kept = 0

    with open(path, "r+") as f:
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


def prune(path, now=None):
    """Drop rows older than MAX_AGE."""
    cutoff = (now or time.time()) - MAX_AGE
    return rewrite(path, lambda t: t >= cutoff)


def serve(data_dir, port, bind="127.0.0.1"):
    path = os.path.join(data_dir, "ping.jsonl")

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=data_dir, **k)

        def log_message(self, *a):
            pass

    def daily():
        while True:
            if os.path.exists(path):
                prune(path)
            time.sleep(86400)

    threading.Thread(target=daily, daemon=True).start()
    ThreadingHTTPServer((bind, port), Handler).serve_forever()


if __name__ == "__main__":
    if sys.argv[1:] == ["--check"]:  # host self-check: python3 history_server.py --check
        import tempfile

        p = tempfile.mktemp()
        line = lambda ts: json.dumps({"tst": "x", "payload": [[t, 1, 0, 1] for t in ts]}) + "\n"
        with open(p, "w") as f:
            f.write(line([100, 200]) + "garbage\n" + line([3000, 4000]))

        assert prune(p, now=200 + MAX_AGE) == 3  # cutoff 200: 100 and garbage go
        assert [json.loads(l)["payload"] for l in open(p)] == [[[200, 1, 0, 1]], [[3000, 1, 0, 1], [4000, 1, 0, 1]]]
        os.remove(p)
        print("ok")
    else:
        serve(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 8000, *sys.argv[3:4])
