"""Ping: ICMP echo quality to PING_TARGET, shown on the Page and Control Page.

Raw lwIP ICMP socket, non-blocking, polled from the main loop each tick
(ADR-0005: no blocking reads). One echo every SEND_MS spreads a batch of
BATCH probes across ~3 s, under the Page's 5 s cycle.

ponytail: replies are reaped on the next loop tick, so RTTs read up to one
tick period (~20 ms) high; timestamp in-payload if that ever matters.
"""

import socket
import struct
import time

SEND_MS = 1_000
TIMEOUT_MS = 800
BATCH = 3  # avg / jitter window: the latest batch
WINDOW = 15  # loss%: rolling, ~5 batches
IDENT = 0x4244  # "BD"; picks our echo replies out of the raw socket

_PAYLOAD = b"buddy-ping--"


def checksum(data):
    """RFC 1071 internet checksum."""

    if len(data) % 2:
        data += b"\x00"

    total = 0
    for i in range(0, len(data), 2):
        total += (data[i] << 8) | data[i + 1]

    while total >> 16:
        total = (total & 0xFFFF) + (total >> 16)

    return ~total & 0xFFFF


def batch_stats(rtts):
    """(avg_ms, jitter_ms) over a batch's successful RTTs; (None, None) if none."""

    if not rtts:
        return None, None

    return sum(rtts) // len(rtts), max(rtts) - min(rtts)


class Pinger:
    """stats: None until the first batch, then (avg_ms, loss_pct, jitter_ms);
    avg/jitter are None when the whole batch was lost."""

    def __init__(self, target):
        self.target = target
        self.sock = None
        self.addr = None
        self.seq = 0
        self.sent_at = None  # ticks_us while an echo is in flight, else None
        self.deadline = 0
        self.next_send = time.ticks_ms()
        self.rtts = []  # successful RTTs of the current batch, ms
        self.settled = 0  # echoes resolved in the current batch
        self.window = []  # last WINDOW outcomes, True = replied
        self.stats = None

    def reset(self):
        """Forget socket and history — the Wi-Fi Link went away or came back."""

        if self.sock:
            self.sock.close()

        self.__init__(self.target)

    def poll(self, now):
        """Advance one tick; True when a batch completed and stats moved."""

        try:
            if self.sock is None:
                self.addr = socket.getaddrinfo(self.target, 1)[0][-1]
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, 1)
                self.sock.setblocking(False)

            if self.sent_at is not None:
                if self._reply():
                    rtt = time.ticks_diff(time.ticks_us(), self.sent_at) // 1000
                    self.rtts.append(rtt)
                    return self._settle(True)

                if time.ticks_diff(now, self.deadline) >= 0:
                    return self._settle(False)

            elif time.ticks_diff(now, self.next_send) >= 0:
                self._send(now)

        except OSError:
            self.reset()  # stale socket after a link drop; rebuilt next poll

        return False

    def _send(self, now):
        self.seq = (self.seq + 1) & 0xFFFF
        head = struct.pack("!BBHHH", 8, 0, 0, IDENT, self.seq)
        head = struct.pack(
            "!BBHHH", 8, 0, checksum(head + _PAYLOAD), IDENT, self.seq
        )
        self.sock.sendto(head + _PAYLOAD, self.addr)

        self.sent_at = time.ticks_us()
        self.deadline = time.ticks_add(now, TIMEOUT_MS)
        self.next_send = time.ticks_add(now, SEND_MS)

    def _reply(self):
        """Drain the socket; True when our echo reply is among the packets."""

        while True:
            try:
                data = self.sock.recv(256)
            except OSError:
                return False

            ihl = (data[0] & 0x0F) * 4  # replies arrive with the IP header

            if len(data) >= ihl + 8 and data[ihl] == 0:  # type 0: echo reply
                ident, seq = struct.unpack_from("!HH", data, ihl + 4)

                if ident == IDENT and seq == self.seq:
                    return True

    def _settle(self, ok):
        self.sent_at = None
        self.settled += 1

        self.window.append(ok)
        if len(self.window) > WINDOW:
            self.window.pop(0)

        if self.settled < BATCH:
            return False

        avg, jitter = batch_stats(self.rtts)
        loss = 100 * (len(self.window) - sum(self.window)) // len(self.window)
        self.stats = (avg, loss, jitter)

        self.rtts = []
        self.settled = 0
        return True


if __name__ == "__main__":  # host self-check: python3 ping.py
    assert checksum(b"\x08\x00\x00\x00\x00\x01\x00\x01") == 0xF7FD
    assert batch_stats([]) == (None, None)
    assert batch_stats([10, 20, 30]) == (20, 20)

    p = Pinger.__new__(Pinger)  # skip __init__: no ticks_ms on host
    p.rtts, p.settled, p.sent_at = [12, 18], 2, 1
    p.window, p.stats = [True] * 13 + [False], None
    assert p._settle(True) and p.stats == (15, 6, 6)
    print("ok")
