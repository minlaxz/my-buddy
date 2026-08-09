import socket
import struct
import time


ICMP_ECHO_REQUEST = 8
ICMP_ECHO_REPLY = 0


def checksum(data):
    if len(data) & 1:
        data += b"\x00"

    total = 0

    for i in range(0, len(data), 2):
        total += (data[i] << 8) | data[i + 1]

    while total >> 16:
        total = (total & 0xFFFF) + (total >> 16)

    return (~total) & 0xFFFF


def _single_ping(address, identifier, sequence, timeout):
    sock = None

    try:
        sock = socket.socket(
            socket.AF_INET,
            socket.SOCK_RAW,
            1,
        )

        sock.settimeout(timeout)

        payload = b"HERMES"

        header = struct.pack(
            "!BBHHH",
            ICMP_ECHO_REQUEST,
            0,
            0,
            identifier,
            sequence,
        )

        packet = header + payload

        packet_checksum = checksum(packet)

        header = struct.pack(
            "!BBHHH",
            ICMP_ECHO_REQUEST,
            0,
            packet_checksum,
            identifier,
            sequence,
        )

        packet = header + payload

        start = time.ticks_us()

        sock.sendto(packet, (address, 0))

        while True:
            data, addr = sock.recvfrom(256)

            if len(data) < 20:
                continue

            ip_header_length = (data[0] & 0x0F) * 4

            if len(data) < ip_header_length + 8:
                continue

            icmp = data[ip_header_length:]

            icmp_type = icmp[0]
            icmp_code = icmp[1]

            reply_id = struct.unpack(
                "!H",
                icmp[4:6],
            )[0]

            reply_sequence = struct.unpack(
                "!H",
                icmp[6:8],
            )[0]

            if (
                icmp_type == ICMP_ECHO_REPLY
                and icmp_code == 0
                and reply_id == identifier
                and reply_sequence == sequence
            ):
                elapsed = time.ticks_diff(
                    time.ticks_us(),
                    start,
                ) / 1000

                ttl = data[8]

                return {
                    "time_ms": elapsed,
                    "ttl": ttl,
                }

    except Exception:
        return None

    finally:
        if sock is not None:
            sock.close()


def ping(
    host="1.1.1.1",
    count=5,
    timeout=2,
    interval=0.1,
):
    address = socket.getaddrinfo(
        host,
        0,
    )[0][-1][0]

    print("Pinging:", address)

    identifier = 0x1234

    results = []

    for sequence in range(1, count + 1):

        result = _single_ping(
            address,
            identifier,
            sequence,
            timeout,
        )

        if result is not None:
            print(
                "Reply:",
                result["time_ms"],
                "ms",
                "TTL:",
                result["ttl"],
            )

            results.append(result)

        else:
            print("Request timed out")

        if sequence < count:
            time.sleep(interval)

    sent = count
    received = len(results)

    if received:
        times = [
            result["time_ms"]
            for result in results
        ]

        ttls = [
            result["ttl"]
            for result in results
        ]

        minimum = min(times)
        maximum = max(times)
        average = sum(times) / received
        average_ttl = sum(ttls) / received

        if len(times) > 1:
            jitter_values = []

            for i in range(1, len(times)):
                difference = abs(
                    times[i] - times[i - 1]
                )

                jitter_values.append(difference)

            jitter = (
                sum(jitter_values)
                / len(jitter_values)
            )
        else:
            jitter = 0

        last_time = times[-1]
        last_ttl = ttls[-1]

    else:
        minimum = None
        maximum = None
        average = None
        average_ttl = None
        jitter = None
        last_time = None
        last_ttl = None

    loss = (
        ((sent - received) / sent) * 100
    )

    result = {
        "host": host,
        "address": address,

        "sent": sent,
        "received": received,
        "loss": loss,

        "min_ms": minimum,
        "avg_ms": average,
        "max_ms": maximum,

        "jitter_ms": jitter,

        "avg_ttl": average_ttl,

        "last_ms": last_time,
        "last_ttl": last_ttl,
    }

    print()
    print("----- Ping Statistics -----")
    print("Sent:", sent)
    print("Received:", received)
    print("Loss:", loss, "%")
    print("Min:", minimum, "ms")
    print("Avg:", average, "ms")
    print("Max:", maximum, "ms")
    print("Jitter:", jitter, "ms")
    print("Avg TTL:", average_ttl)
    print("---------------------------")

    return result
