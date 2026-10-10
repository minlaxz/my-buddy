"""Serve the History page and its data, read-only. Started by history.sh.

GET  /                                  history.html (symlinked as index.html)
GET  /ping?from=S&to=S&step=S           rows in [from, to) averaged per step, as JSON:
                                        [[t, batches, answered, avg, jitter, loss, worst], ...]
                                        one per non-empty interval, intervals counted from `from`
                                        (unix seconds), avg/jitter/worst null when all were lost

Rows older than MAX_AGE (6 months) are dropped at start and once a day.
"""

import json
import os
import sys
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from ingest import connect


MAX_AGE = 183 * 86400  # 6 months

# avg() and max() skip NULLs, so avg/jitter/worst cover only the answered batches
BUCKETS = """SELECT :from + (t - :from) / :step * :step AS k, count(*), count(avg),
  avg(avg), avg(jitter), avg(loss), max(avg)
  FROM ping WHERE t >= :from AND t < :to GROUP BY k ORDER BY k"""


def buckets(db, frm, to, step):
    return db.execute(BUCKETS, {"from": frm, "to": to, "step": step}).fetchall()


def prune(db, now=None):
    """Drop rows older than MAX_AGE; returns how many went."""
    with db:
        return db.execute("DELETE FROM ping WHERE t < ?", ((now or time.time()) - MAX_AGE,)).rowcount


def serve(data_dir, port, bind="127.0.0.1"):
    path = os.path.join(data_dir, "ping.db")
    connect(path).close()  # schema and WAL before the first request

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=data_dir, **k)

        def do_GET(self):
            url = urlsplit(self.path)
            if url.path != "/ping":
                if url.path.startswith("/ping."):  # the DB and its WAL files are not for download
                    return self.send_error(404)
                return super().do_GET()
            try:
                q = {k: int(v[0]) for k, v in parse_qs(url.query).items()}
                frm, to, step = q["from"], q["to"], max(1, q["step"])
            except (KeyError, ValueError):
                return self.send_error(400, "need integer from, to, step")
            db = connect(path)  # one per request: sqlite connections stay on their thread
            try:
                body = json.dumps(buckets(db, frm, to, step), separators=(",", ":")).encode()
            finally:
                db.close()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    def daily():
        while True:
            db = connect(path)
            prune(db)
            db.close()
            time.sleep(86400)

    threading.Thread(target=daily, daemon=True).start()
    ThreadingHTTPServer((bind, port), Handler).serve_forever()


if __name__ == "__main__":
    if sys.argv[1:] == ["--check"]:  # host self-check: python3 history_server.py --check
        import tempfile
        from ingest import ingest

        p = os.path.join(tempfile.mkdtemp(), "ping.db")
        db = connect(p)
        line = lambda rows: json.dumps({"tst": "x", "payload": rows}) + "\n"
        lines = [line([[100, 10, 0, 2], [110, None, 100, None]]), "garbage\n", line([[100, 99, 0, 9], [130, 30, 20, 4]])]

        assert ingest(db, lines) == 3  # garbage skipped, the second t=100 ignored
        assert ingest(db, lines) == 0  # migrating the same file twice adds nothing
        # step 20 from 95: [95,115) holds 100 and 110 (one lost), [115,135) holds 130
        assert buckets(db, 95, 200, 20) == [(95, 2, 1, 10.0, 2.0, 50.0, 10), (115, 1, 1, 30.0, 4.0, 20.0, 30)]
        assert buckets(db, 95, 130, 20) == [(95, 2, 1, 10.0, 2.0, 50.0, 10)]  # `to` excluded
        assert prune(db, now=110 + MAX_AGE) == 1  # cutoff 110: only 100 goes
        print("ok")
    else:
        serve(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 8000, *sys.argv[3:4])
