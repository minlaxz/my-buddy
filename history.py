"""History: Ping batches kept on the Terminal until the Mac is listening.

Every landed batch becomes a 9-byte record in RAM; records are appended to
FILE every FLUSH_MS, so a power cut loses at most that much. The main loop
drains them over the Relay, CHUNK records per publish, while the Mac's
recorder says it is listening (retained bud/history = on).

ponytail: a drain loads the whole backlog into RAM (8 MB PSRAM; a week is
~1.8 MB). Stream from the file instead if a board without PSRAM shows up.
"""

import os
import struct
import time

FILE = "history.bin"
REC = "<IHBH"  # unix s, avg ms, loss %, jitter ms
REC_SIZE = struct.calcsize(REC)
LOST = 0xFFFF  # avg / jitter when the whole batch was lost
FLUSH_MS = 5 * 60_000
CHUNK = 50  # records per publish, ~1.1 KB of JSON
MAX_RECORDS = 7 * 24 * 1200  # a week at a batch every 3 s

# MicroPython on ESP32 counts seconds from 2000-01-01; the Mac wants 1970.
EPOCH_OFFSET = 946_684_800 if time.gmtime(0)[0] == 2000 else 0


def pack(stats, t):
    avg, loss, jitter = stats
    return struct.pack(
        REC,
        t + EPOCH_OFFSET,
        LOST if avg is None else min(avg, LOST - 1),
        min(loss, 255),
        LOST if jitter is None else min(jitter, LOST - 1),
    )


def to_json(data):
    """JSON array of [t, avg, loss, jitter] rows; null avg/jitter = batch lost."""

    rows = []
    for i in range(0, len(data), REC_SIZE):
        t, avg, loss, jitter = struct.unpack_from(REC, data, i)
        rows.append(
            "[{},{},{},{}]".format(
                t, "null" if avg == LOST else avg, loss, "null" if jitter == LOST else jitter
            )
        )
    return "[" + ",".join(rows) + "]"


class History:
    def __init__(self, path=FILE):
        self.path = path
        self.buf = bytearray()  # recorded, not yet in the file
        self.pending = b""  # loaded for a drain in progress
        self.off = 0  # how much of pending has gone out
        self.next_flush = time.ticks_add(time.ticks_ms(), FLUSH_MS)

        try:
            self.on_disk = os.stat(path)[6] // REC_SIZE
        except OSError:
            self.on_disk = 0

    @property
    def count(self):
        return (
            self.on_disk
            + len(self.buf) // REC_SIZE
            + (len(self.pending) - self.off) // REC_SIZE
        )

    def record(self, stats):
        """Keep a landed batch. Skipped until the Clock has synced: no honest time before."""

        if time.localtime()[0] < 2025:
            return

        self.buf += pack(stats, int(time.time()))

    def poll(self, now):
        if time.ticks_diff(now, self.next_flush) >= 0:
            self.next_flush = time.ticks_add(now, FLUSH_MS)
            self.flush()

    def flush(self):
        if self.buf:
            with open(self.path, "ab") as f:
                f.write(self.buf)
            self.on_disk += len(self.buf) // REC_SIZE
            self.buf = bytearray()

        # ponytail: over the cap, keep the newest half — a rare whole-file
        # rewrite beats trimming on every flush.
        if self.on_disk > MAX_RECORDS:
            with open(self.path, "rb") as f:
                f.seek((self.on_disk - MAX_RECORDS // 2) * REC_SIZE)
                keep = f.read()
            with open(self.path, "wb") as f:
                f.write(keep)
            self.on_disk = len(keep) // REC_SIZE

    def next_chunk(self):
        """JSON for the next CHUNK records, or None when nothing is held.
        The first call of a drain loads the backlog (file, then RAM)."""

        if self.off >= len(self.pending):
            self.pending, self.off = self._load(), 0
            if not self.pending:
                return None

        end = min(self.off + CHUNK * REC_SIZE, len(self.pending))
        chunk = self.pending[self.off : end]
        self.off = end

        if self.off >= len(self.pending):
            self.pending, self.off = b"", 0

        return to_json(chunk)

    def abort(self):
        """Drain interrupted: put what has not gone out back in front of the new records."""

        self.buf = bytearray(self.pending[self.off :]) + self.buf
        self.pending, self.off = b"", 0

    def _load(self):
        data = b""

        if self.on_disk:
            with open(self.path, "rb") as f:
                data = f.read()
            os.remove(self.path)
            self.on_disk = 0

        data += self.buf
        self.buf = bytearray()
        return data


if __name__ == "__main__":  # host self-check: python3 history.py
    import tempfile

    for n in ("ticks_ms", "ticks_add", "ticks_diff"):
        setattr(time, n, lambda *a: 0)

    assert REC_SIZE == 9
    assert to_json(pack((12, 6, 3), 100)) == "[[{},12,6,3]]".format(100 + EPOCH_OFFSET)
    assert to_json(pack((None, 100, None), 1)) == "[[{},null,100,null]]".format(1 + EPOCH_OFFSET)

    path = tempfile.mktemp()
    h = History(path)
    for i in range(CHUNK + 2):
        h.record((i, 0, 0))
    assert h.count == CHUNK + 2 and h.on_disk == 0

    h.flush()
    assert h.on_disk == CHUNK + 2 and not h.buf
    h.record((99, 0, 0))
    assert History(path).on_disk == CHUNK + 2  # survives a reboot

    first = h.next_chunk()  # loads file + RAM, hands out CHUNK
    assert first.count("[") == CHUNK + 1 and h.count == 3 and h.on_disk == 0
    h.abort()
    assert h.count == 3 and h.pending == b"" and len(h.buf) == 3 * REC_SIZE
    assert h.next_chunk().count("[") == 4 and h.count == 0
    assert h.next_chunk() is None

    h.on_disk = MAX_RECORDS + 1  # cap: pretend the file is huge, flush trims to the newest half
    with open(path, "wb") as f:
        f.write(pack((0, 0, 0), 0) * (MAX_RECORDS + 1))
    h.flush()
    assert h.on_disk == MAX_RECORDS // 2

    os.remove(path)
    print("ok")
