"""Store Ping chunks in the History DB. Started by history.sh; also the JSONL migration.

  mosquitto_sub -F %J ... | python3 ingest.py ping.db     live, one chunk per line
  python3 ingest.py ping.db ping.jsonl                    migrate an old JSONL, any number of times

Each line is one chunk: {"payload":[[unix_s, avg_ms|null, loss_pct, jitter_ms|null], ...], ...}.
A row whose timestamp is already stored is skipped, so a re-drain or a second
migration of the same file adds nothing. Lines that do not parse are skipped.
"""

import fileinput
import json
import sqlite3
import sys


def connect(path):
    db = sqlite3.connect(path)
    db.execute("PRAGMA journal_mode=WAL")  # the server reads while this writes
    db.execute("PRAGMA synchronous=NORMAL")
    db.execute("CREATE TABLE IF NOT EXISTS ping (t INTEGER PRIMARY KEY, avg INTEGER, loss INTEGER, jitter INTEGER)")
    return db


def ingest(db, lines):
    """Insert every row of every chunk in `lines`; returns the number of new rows."""
    added = 0
    for line in lines:
        try:
            rows = [tuple(r[:4]) for r in json.loads(line)["payload"]]
            with db:  # one commit per chunk: a chunk is never half stored
                added += db.executemany("INSERT OR IGNORE INTO ping VALUES (?,?,?,?)", rows).rowcount
        except (ValueError, KeyError, TypeError, sqlite3.Error):
            continue
    return added


if __name__ == "__main__":
    db = connect(sys.argv[1])
    try:
        n = ingest(db, fileinput.input(sys.argv[2:]))
    except KeyboardInterrupt:  # Ctrl-C on history.sh reaches this too
        sys.exit(130)
    if sys.argv[2:]:
        total = db.execute("SELECT count(*) FROM ping").fetchone()[0]
        print(f"added {n} rows, {total} in {sys.argv[1]}")
