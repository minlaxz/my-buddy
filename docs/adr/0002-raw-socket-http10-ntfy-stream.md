# Keep the raw-socket HTTP/1.0 ntfy stream

`ntfy.py` subscribes with a hand-built request over a raw socket. Three details look like oversights and are not:

**It does not use `urequests`.** `urequests` has no non-blocking read. The Terminal's main loop drives the animation, the ping countdown and the Page redraws on every tick, so a blocking read on a stream that is silent for forty-five seconds at a time would freeze the display. The socket is set non-blocking and polled once per tick instead.

**It requests HTTP/1.0, not 1.1.** HTTP/1.0 forbids chunked transfer-encoding, so the response body arrives as plain newline-delimited JSON. Under 1.1 the reader would have to strip chunk-size lines, which the line parser does not do — it would feed them to `json.loads` as garbage. The server answers `HTTP/1.1 200` regardless; what matters is that it does not chunk.

**It sends `User-Agent: curl/8.7.1`.** The ntfy host sits behind Cloudflare, which answers `error code: 1010` and blocks the request before it reaches ntfy when it does not recognise the client. This is a workaround for the edge, not a requirement of ntfy. Any script talking to the same host needs it too; Python's default urllib agent is blocked.

## Consequences

- If the server or its proxy ever forces chunked encoding, the parser breaks with malformed-JSON logs rather than a clean error. The fix would be to handle chunk framing, not to switch to `urequests`.
- The connect path blocks for the DNS, TCP and TLS handshake. The five-second reconnect backoff exists to bound how long the main loop can stall on a dead link, not merely to be polite to the server.
- The pinned User-Agent may need revisiting if Cloudflare's rules change. It is a string the edge accepts today, not a contract.
- A non-200 status line is logged and the connection dropped. Without that check an authorization failure parses as valid headers and then goes quiet, which is indistinguishable from a healthy but idle topic — this cost real debugging time once already.
