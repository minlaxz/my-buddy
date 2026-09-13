# Ping history: external storage and graphs

Research date: **2026-09-13**. Scope: compare approaches for this Terminal, not implement or select a deployment. Repository observations below come from the checked-out files. External capability claims use official primary sources listed at the end. No credentials, accounts, hardware, broker settings, or paid services were inspected or changed.

## Recommendation

**Minimum push solution: publish structured Ping batches through the existing MQTT connection to a small external collector, store them in a local SQLite file, and serve a simple browser history chart.** This reuses the Terminal's TLS/client plumbing without requiring Telegraf, InfluxDB, or Grafana. It still needs a new telemetry topic and ACL, bounded publishing, a collector running on an always-on host, and a decision about delivery guarantees. The current Receipt path is not a telemetry queue.

**If the main purpose is diagnosing internet outages, prefer Terminal HTTP POST → a collector on the same LAN → SQLite → browser charts**, or a local MQTT broker with the same SQLite collector. Sending through the existing cloud broker shares the WAN failure being measured. A local receiver can capture failed internet probes while Wi-Fi/LAN remain usable. Neither approach receives data while Wi-Fi itself is down without later device replay.

For an exploratory baseline with **zero firmware changes**, a local host can poll the existing `GET /status` roughly every five seconds and store snapshots in SQLite or CSV. This is useful for discovering what charts the owner wants, but is pull, not Terminal-sent logs, and cannot provide an exact event history. Do not present that baseline as a reliable ping recorder.

Move to MQTT → Telegraf → InfluxDB → Grafana only when its dashboard/query/retention conveniences justify operating the additional services, or they already exist. Choose hosted ThingSpeak when avoiding a collector is more important than full-resolution, WAN-independent recording.

## What this project actually measures and exposes

| Constraint | Evidence and implication |
| --- | --- |
| Hardware and scope | [`CONTEXT.md`](../../CONTEXT.md) describes one ESP32-S3 Terminal with a 240×240 TFT. There is no separate historical backend today. Free heap, flash capacity, exact installed MicroPython build, and always-on host availability were not measured. |
| Probe timing | [`config.py`](../../config.py) targets the raw IP `8.8.8.8`. [`ping.py`](../../ping.py) schedules an echo every 1,600 ms with a 1,000 ms timeout, at most one in flight. Three settled probes complete a batch, nominally about 4.8 seconds between batches in steady state, not a guaranteed schedule. |
| Metric definitions | `batch_stats()` averages successful integer-millisecond RTTs with integer truncation. “Jitter” is **max RTT minus min RTT among successes in the latest batch**, not standard deviation or a successive-packet jitter estimator. Loss is an integer-truncated percentage over the latest **up to 15** settled outcomes. Average/jitter are null when a batch has no replies. One success gives zero range, not evidence of stable latency. |
| Loss of detail | `_settle()` clears batch RTTs and exposes only `(avg_ms, loss_pct, jitter_ms)`. It does not expose batch sent/received counts, raw probes, sample ID, or sample time. Rolling-loss windows overlap. Historical averages of displayed loss percentages are not exact packet-loss rates. |
| Reset and missing data | [`main.py`](../../main.py) only polls the Pinger while a link is shown and resets it on disconnected/connected state transitions. Socket errors also reset it. There are no probes during known Wi-Fi loss, so absence is not “100% ICMP loss.” Initial stats are null. |
| Existing HTTP | `status()` and [`web.py`](../../web.py) provide `GET /status` with `ping.avg_ms`, `loss_pct`, `jitter_ms`, `uptime_s`, and link information. It is a latest-value snapshot, not an append-only feed. Repeated values might be a new identical batch or a stale batch. Polling can miss batches and cannot reliably deduplicate by value. |
| Timing interference | The main loop sleeps 20 ms and reaps replies on a later poll. The code's comment notes roughly one tick of RTT bias, but TLS connect, NTP, Wi-Fi reconnect, web handling, and display work can cause **larger** stalls. New synchronous upload work would distort the measurement further. |
| Existing MQTT | [`relay.py`](../../relay.py) uses a CA-verified TLS connection on 8883, a fixed `buddy-terminal` client ID, inbound retained Message/LED topics, and outbound non-retained Receipts. It currently publishes no ping history. [`ADR-0006`](../adr/0006-relay-over-mqtt-beside-control-page.md) documents a HiveMQ Cloud experiment and a 2026-09-24 review/delete condition if unused. Do not silently make that experiment a mandatory dependency. |
| Authorization and delivery | ADR-0006 documents Terminal publication restricted to `bud/+/ack`. A distinct telemetry topic needs an ACL update, not misuse of Receipt topics. [`lib/umqtt/simple.py`](../../lib/umqtt/simple.py) defaults to clean sessions and QoS 0. QoS 1 publishing waits for an acknowledgement with `wait_msg()`, which can block the loop. There is no durable outbox. Broker configuration was not independently checked. |
| Clock and security | NTP is attempted on link-up and every six hours after success, with minute retries after failure. The displayed clock applies Yangon +06:30. [`ADR-0005`](../adr/0005-raw-socket-http-control-page.md) explicitly trusts the LAN and has no authentication. Do not expose the existing Control Page through public port forwarding. |

## Option comparison

### 1. Serial → host CSV → historical plots

**Path:** Terminal emits one distinguishable, newline-delimited telemetry record per completed batch → a USB-connected host reads lines → Python `csv.DictWriter` appends records → a host-side plot or browser page reads the CSV.

pySerial documents newline reads, timeout handling, and port enumeration. A timed-out partial line must not become a corrupt CSV row. Python's CSV module handles quoting and recommends opening CSV files with `newline=''`. [S1, S2]

- **Firmware change:** add structured batch emission. Existing `print()` messages are diagnostics, not Ping results. Prefix telemetry or use a separate stream so boot/Wi-Fi/Relay messages are not parsed as samples.
- **Best fit:** a desk unit that stays plugged into an awake Mac or other host, initial investigations, and capturing WAN or Wi-Fi failures without needing a working network transport.
- **Limits:** a sleeping/disconnected host creates gaps. Serial is not a durable queue. Confirm the board's actual USB/serial interface and coexistence with REPL/deployment tools. An unbounded print can also block. Host file flushing, rotation, backups, and handling a partial last row need explicit policies.
- **Charts:** CSV is storage/export, not a dashboard. Add a small read-only browser graph or periodically generated plot. For durable deduplication and flexible historical queries, SQLite is usually a better next step than a pile of CSV files.
- **Cost:** no hosted ingestion subscription is inherent in this path. Hardware, power, disk, backups, and maintenance are still costs. No paid product quote was verified.

### 2. HTTP → local SQLite + dashboard

**Path:** Terminal POSTs a bounded event/batch to a LAN collector → collector validates and commits it in SQLite → collector serves chart data and a simple browser history page. SQLite belongs on the host, not on the ESP32. SQLite's official guidance specifically supports application-local storage, analysis, and application-specific server-side databases. Keep the file on the collector's local disk rather than having clients concurrently access a network filesystem. [S3]

- **Firmware change:** outbound HTTP client/sender plus an outbox and retry state. The current `WebServer` is inbound-only, not an upload implementation. Retain the polled architecture, with bounded timeouts and bounded work per loop iteration.
- **Collector contract:** authenticate writes, limit payload sizes, validate types/ranges/version, and enforce a unique event key. Return success only after transaction commit. A retry of an already committed key should succeed without inserting another row. Keep writes serialized and charts read-only. Back up the database using a SQLite-aware approach.
- **Best fit:** one Terminal and a host that is normally on. Works through WAN outages while the LAN and collector survive. Few moving parts, easy CSV export, and no cloud account requirement.
- **Limits:** requires a stable LAN address/name and host availability. Plain HTTP on a trusted isolated LAN has no confidentiality and bearer credentials can be observed. For untrusted networks use verified HTTPS or a protected network path, not public exposure of the Terminal's current control server.
- **No-firmware baseline:** host polling `/status` can use the same storage/chart layer, but store `received_at_utc`, fetch status, and `kind=status_snapshot`. Explicitly label charts “observed snapshots.” A failed HTTP request means collection failure, not proof that ICMP probes failed. Equal consecutive snapshots are not safe to collapse as duplicates.

### 3. MQTT → Telegraf → InfluxDB → Grafana

**Path:** Terminal publishes non-retained telemetry on a new narrowly authorized topic such as `bud/<device_id>/ping` → broker → Telegraf `mqtt_consumer` → InfluxDB → Grafana.

Official Telegraf documentation verifies MQTT subscriptions, TLS, configurable data parsers, QoS, persistent sessions, and tracking acknowledgements after output delivery. Its `influxdb_v2` output writes to InfluxDB 2.x using a URL, token, organization, and bucket. Grafana documents an included InfluxDB data source, historical dashboards, and alerting. [S4–S6]

- **Concrete compatibility baseline:** InfluxDB **2.x** with Telegraf's `influxdb_v2` output and Grafana's corresponding supported query configuration. Pin and test actual versions. Do not combine instructions for InfluxDB 2.x/Flux with an arbitrary InfluxDB 3 deployment just because the product name is similar.
- **Benefit:** richer time-range queries, multiple panels/devices, centralized retention, and alerts. The board only produces telemetry. Collection/storage/UI run elsewhere.
- **Burden:** broker access, Telegraf parser/output configuration, database storage/backups, retention policies, Grafana provisioning/security, and version compatibility. This is disproportionate for a single chart unless the services already exist.
- **Durability:** QoS 0 permits loss. QoS 1 permits duplicates, so event identity remains necessary. Retained messages hold the latest value on a topic, **not history**. A broker acknowledgement is not proof that SQLite/InfluxDB committed an event. [S7]
- **Consumer outages:** Telegraf documents using a stable client ID, `persistent_session`, and QoS 1/2, with matching publisher QoS, to receive queued messages after subscriber downtime. Broker session retention, quotas, persistence, and expiration still need checking. Its `max_undelivered_messages` is finite backpressure, not an unlimited archive. [S4]
- **Terminal outages:** broker persistence cannot store events the Terminal never transmitted. The current client does not supply a durable retry mechanism merely by changing `qos=1`, and its blocking acknowledgement wait needs redesign or strict bounding before use here.
- **Minimal variant:** omit Telegraf/InfluxDB/Grafana and use a small MQTT subscriber writing SQLite. This is the minimum push recommendation when the existing cloud route is acceptable. A local broker improves WAN-outage fidelity but introduces another service.
- **Cost:** no managed-service price or existing HiveMQ quota was verified. Self-hosting avoids a required managed ingestion bill but still consumes host resources and operational time. Obtain actual plan limits before relying on broker offline queues or cloud retention.

### 4. Hosted ThingSpeak

**Path:** Terminal, or preferably a local collector forwarding summaries, writes channel fields to ThingSpeak → hosted channel storage and visualizations. MathWorks documents REST/MQTT ingestion and up to eight fields per message. Channels are private by default, with optional public sharing. [S8, S9]

**Verified advertised limits on the research date:** the licensing FAQ says free use is for non-commercial users, with at most **3 million messages/year**, **4 channels**, a **15-second per-channel update interval**, and at most **3,000 bytes per message**. Commercial use beyond a time-limited evaluation requires a commercial license. The FAQ describes paid options with a one-second update interval, but no paid currency price is quoted here. Eligibility and plan terms must be rechecked before use. [S8]

The Terminal's nominal 4.8-second batch cadence produces approximately **18,000 batch events/day**, or **6.57 million per 365-day year**, if continuously active. Directly posting every batch conflicts with the free rate and annual allowances. A proposed **30-second summary** is 1,051,200 writes per 365-day year for one channel, before retries that create extra records, other channels, or derived writes. This arithmetic is a planning estimate, not a throughput guarantee.

- Use non-overlapping summary counts and successful RTT sums, not averaged rolling-loss percentages. Suggested numeric fields: sent, received, RTT sum, RTT min, RTT max, displayed rolling loss, RSSI, and telemetry-drop count. Define null handling and a separate mapping for identity/time before implementation.
- Hosted charts reduce local operations, but WAN failure blocks upload exactly when the history matters. A local forwarder with a disk spool keeps rich raw data and sends lower-resolution summaries after connectivity returns.
- **Unverified API details:** official write and bulk-write pages returned HTTP 403, including a regional retry. Therefore timestamp/backfill formats, duplicate behavior, bulk-write limits, and retry semantics are **not established by this research**. Do not promise reliable offline replay to ThingSpeak until these are verified. The accessible licensing and overview pages are sufficient for this high-level comparison, not an implementation specification.

## Proposed event contract

This is a design proposal, not a claim that the firmware already emits these fields. Prefer one record per **non-overlapping completed batch**, emitted once at `_settle()` completion, with optional raw probe records if percentiles or forensic detail become necessary. Before a Wi-Fi or socket reset discards a partial batch, preserve its settled outcomes and mark any in-flight probe as interrupted/unknown rather than silently dropping it or inventing a timeout. Keep attempted, settled, and interrupted counts distinct when claiming coverage or exact loss.

| Field | Meaning |
| --- | --- |
| `schema_version`, `kind` | Versioned contract, e.g. `1`, `ping_batch`. Separate kinds for `link_state`, `telemetry_gap`, and exploratory `status_snapshot`. |
| `device_id`, `boot_id`, `event_seq` | Stable non-secret device identity, new identity per boot, monotonically increasing event sequence. Composite unique key for idempotent replay. Do not use the 16-bit ICMP sequence as a globally unique event ID. |
| `target`, `probe_interval_ms`, `timeout_ms` | Measurement destination and settings. Changes must not silently merge into the same historical interpretation. |
| `window_start_uptime_ms`, `window_end_uptime_ms` | Monotonic, wrap-safe accumulated elapsed time for the observed batch. Not raw `ticks_ms()` values treated as Unix time. |
| `measured_at_utc`, `clock_status`, `last_sync_age_s` | UTC batch-end time or null, with `unsynced`/`synced`/`holdover` quality and age of successful synchronization. |
| `received_at_utc` | Assigned by collector on arrival, separately from measurement time. |
| `sent`, `received`, `rtt_sum_ms`, `rtt_min_ms`, `rtt_max_ms` | Exact non-overlapping counts and aggregates. All-loss batch: sent > 0, received = 0, RTT sum = 0, min/max = null. Preserve pre-rounded sums for later aggregation. |
| `avg_ms`, `jitter_range_ms`, `rolling_loss_pct`, `rolling_window_count` | Optional display-compatible values, explicitly distinguished from exact batch statistics. Rolling count is at most 15 and lower after startup/reset. |
| `link_up`, `rssi_dbm`, `dropped_events_total` | Context and instrumentation of telemetry loss. Avoid SSID, IP, credentials, and message text unless required. |

For graph buckets of settled probes, compute **loss = 100 × (sum(sent) − sum(received)) / sum(sent)**, undefined when no settled probes were recorded. Here `sent` counts attempts with a known reply/timeout outcome in the batch. Report interrupted/unknown attempts separately and exclude them from this denominator. Compute mean RTT as **sum(rtt_sum_ms) / sum(received)**, null with no successes. Do not average per-batch averages without weighting. Max-minus-min can be combined from extrema but must be labeled with its actual window. Median/p95 RTT cannot be recovered from only count/sum/extrema.

Show separate latency, packet-loss, and collection-coverage panels. Plot gaps instead of zero latency or interpolated healthy lines. Distinguish Wi-Fi-down/no-probes, ICMP timeouts while linked, reboot/reset, unsynced time, and missing uploads. ICMP to one public IP measures that path and endpoint response policy, not universal application availability.

## Outage buffering and time semantics

1. **Capture first, send later.** Push a small event into a bounded RAM ring without doing network I/O inside Ping settlement. Drain a bounded amount outside the timing-sensitive operation. Exponential reconnect backoff with jitter and a maximum work budget prevents catch-up traffic starving Ping and the Page.
2. **Size for a declared outage.** At a nominal batch every 4.8 seconds, five minutes is about 63 events. At an illustrative 300 serialized bytes/event that is about 19 KB of payload alone, excluding Python object and queue overhead. Do not assume that heap is available. Measure the actual encoded size and heap headroom before choosing capacity. Raw probes increase the rate roughly threefold.
3. **Define overflow and reboot behavior.** RAM buffering loses data on power failure. A bounded flash spool could survive reboot but needs wear-aware batched writes, crash recovery, and a storage budget. Neither exists today. For a first version, explicitly accept bounded RAM retention, drop oldest on overflow to preserve recent diagnostics, and report the drop count and affected range. An always-on local collector should use durable disk storage after receipt.
4. **Replay without duplication.** Preserve event IDs and measurement time through retries. For HTTP, acknowledge after commit. For MQTT, distinguish transport PUBACK from an optional application-level persisted acknowledgement. End-to-end lossless claims require an outbox and recovery policy at every hop, not just QoS 1. Bound and rate-limit backfill, including hosted quotas.
5. **Keep UTC and elapsed time separate.** MicroPython documents port-dependent epochs and wrapping tick counters. Detect the firmware epoch using `gmtime(0)[0]` or emit an explicitly constructed UTC timestamp. Do not send raw embedded `time.time()` as assumed Unix seconds. Use `ticks_diff`/`ticks_add` within their documented half-period validity and accumulate short elapsed intervals for long-lived uptime. The current one-shot `ticks_diff(now, boot_tick)` status uptime is not a permanent unique clock. [S10]
6. **Do not invent timestamps before NTP.** Keep `measured_at_utc=null` while unsynchronized, plus boot-relative elapsed time and collector arrival time. A later sync anchor may reconstruct earlier timestamps within the same boot, labeled estimated and subject to oscillator error. NTP can step wall time, so ordering and RTT duration must rely on monotonic sequence/elapsed time. Yangon +06:30 belongs in presentation, not stored UTC. After sync, offline time is holdover, not freshly verified time.

## Verification and remaining decisions

This was documentation research and source inspection only. No packages were installed, no telemetry was sent, no tests or device experiments were run, and no deployment was selected. Integration discovery was consulted before researching external alternatives, with no catalog candidate fitting this comparison and no product commitment.

Before implementation, confirm the collector host can stay awake, whether WAN-outage recording is the priority, required offline retention, current broker ACL/plan/persistence, real firmware memory and timing budget, and whether exact raw-probe percentiles are needed. Acceptance should then exercise all-loss batches, Wi-Fi loss, WAN-only loss, collector/database downtime, duplicates, queue overflow, reboot, NTP failure/steps, tick rollover, and measured RTT bias during backfill.

### Delivery verification

The coordinator read the committed Markdown artifact and exercised all nine relative documentation/code links against the real repository. All resolved to existing files. Recalculation confirmed 18,000 nominal batches/day, 6,570,000/year, and 1,051,200 summaries/year at 30 seconds. The commit contained only this research note, leaving firmware and unrelated files unchanged. These checks establish a navigable, internally consistent research deliverable, not a functioning telemetry system.

An independent follow-up request to the MathWorks licensing FAQ returned HTTP 403. Its advertised limits above rely on the research worker's successful retrieval, not a second independent retrieval. Treat plan terms as deployment-time checks. No device address, running collector, or deployed history UI was established during this research, so end-to-end ingestion, persistence, replay, and graphs were not exercised. Building or deploying that path would exceed the explicit instruction not to implement. Actual runtime superiority remains unverified. The recommendation reduces proposed components relative to the full dashboard stack, but no performance or reliability improvement has been measured.

## Official sources checked

All sources below were retrieved on **2026-09-13**. Live documentation can change. `latest` and `master` pages describe their current documentation branches, not a verified installed version.

- **[S1]** [pySerial short introduction](https://pyserial.readthedocs.io/en/latest/shortintro.html): serial ports, newline reads, partial/time-out behavior, and enumeration.
- **[S2]** [Python `csv` documentation](https://docs.python.org/3/library/csv.html): `DictWriter`, quoting, newline handling, and null-to-empty-string behavior. Define CSV null semantics explicitly.
- **[S3]** [SQLite: Appropriate Uses](https://www.sqlite.org/whentouse.html): local storage, data analysis, application-server use, and client/server versus local-file tradeoffs.
- **[S4]** [Telegraf MQTT consumer, official repository README](https://github.com/influxdata/telegraf/blob/master/plugins/inputs/mqtt_consumer/README.md), verified via [raw source](https://raw.githubusercontent.com/influxdata/telegraf/master/plugins/inputs/mqtt_consumer/README.md): tracking acknowledgements, persistent sessions, QoS, TLS, and parser configuration. The documentation-site fetch returned an unreadable compressed body, so the repository source was used instead.
- **[S5]** [Telegraf InfluxDB v2 output, official repository README](https://github.com/influxdata/telegraf/blob/master/plugins/outputs/influxdb_v2/README.md), verified via [raw source](https://raw.githubusercontent.com/influxdata/telegraf/master/plugins/outputs/influxdb_v2/README.md): 2.x target, bucket/org/token, and preservation of timestamps.
- **[S6]** [Grafana InfluxDB data source](https://grafana.com/docs/grafana/latest/datasources/influxdb/): included data source, queries, dashboards, and alerting. Version compatibility must still be checked at deployment.
- **[S7]** [OASIS MQTT 3.1.1 specification](https://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html): QoS (§4.3), retained messages (§3.3.1.3), clean sessions (§3.1.2.4), and acknowledgement scope.
- **[S8]** [MathWorks ThingSpeak licensing FAQ](https://thingspeak.mathworks.com/pages/license_faq): free eligibility, message/channel/rate limits, field count, payload size, and paid interval. No paid price or contractual service guarantee inferred.
- **[S9]** [MathWorks ThingSpeak: Collect, Analyze, Act](https://thingspeak.mathworks.com/pages/how_to): hosted channel storage, default privacy, analysis, and visualization.
- **[S10]** [MicroPython `time` documentation](https://docs.micropython.org/en/latest/library/time.html): epoch detection, RTC prerequisites, tick wrapping, and half-period arithmetic constraints.

Attempted but **not verified** because of HTTP 403: MathWorks [Write Data](https://www.mathworks.com/help/thingspeak/writedata.html), [Bulk-Write JSON Data](https://www.mathworks.com/help/thingspeak/bulkwritejsondata.html), and regional variants. No claims about those APIs' precise backfill or timestamp behavior are based on inaccessible pages.
