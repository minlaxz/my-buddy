# History is stored in SQLite and the page loads only its Range

Status: accepted, 2026-10-10. Amends ADR-0007 (JSONL on disk, the whole file fetched by the page) and ADR-0008.

At one batch every 3 s the JSONL was 9.9 MB after five days, and the page downloaded and parsed all of it every 30 s. Six months of retention would be ~330 MB per refresh. ADR-0007 named "SQLite, or rotate" as the upgrade when that bit.

**Write path.** `history.sh` still runs `mosquitto_sub -F %J` in its reconnect loop, but its output goes through process substitution into `receiver/ingest.py`, which inserts each chunk's rows into `ping.db` in one transaction. Process substitution, not a pipe, so `$!` stays `mosquitto_sub`'s pid for the `kill -9` that fires the will. One table, `ping(t INTEGER PRIMARY KEY, avg, loss, jitter)`, with `INSERT OR IGNORE`: a batch drained twice (Terminal rebooted mid-drain) is stored once. WAL mode lets the server read while the recorder writes. The stdlib `sqlite3` module is already in the image's Python; no new dependency.

**Read path.** `GET /ping?from=&to=&step=` averages in SQL and returns one row per non-empty interval (batches, answered, avg, jitter, loss, worst). The page asks for its Range only; a week at 30 min is ~20 KB. Intervals are counted from a `from` the page aligns to local midnight, so hourly and daily points sit on local hours in Yangon's +06:30. Stats between two pins are weighted from those intervals, not from raw rows. The DB and any leftover `ping.jsonl.bak` in `/data` are refused (404); only the page and `/ping` are served.

**Migration is the same script.** `ingest.py ping.db ping.jsonl` reads a JSONL instead of stdin. Duplicates are skipped, so running it twice, or while the Recorder writes, is safe. The VPS's 151k rows took 1.4 s and shrank from 9.9 MB to 2.4 MB.

Rejected: keeping the JSONL as the write log and copying it into SQLite on a timer (two stores to prune, drift between them); paho-mqtt in Python (a dependency, and the reconnect and will logic rewritten); returning raw rows and averaging in the browser (fine for a day, megabytes for a month); rotating JSONL files per day (still a full parse per Range, and the page would need to know file names).
