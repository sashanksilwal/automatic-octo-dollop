# Part A stream protocol, version 1

Each hop uses an HTTP GET connection. The glasses listen on 8080 by default; the phone on 8081. Requests require `Authorization: Bearer PAIRING_CODE`. Redirects are rejected by clients. URLs must be a base HTTP(S) address without credentials, query parameters, or an arbitrary path.

## Endpoints

- `GET /status`: JSON containing protocol version, state, cumulative received frames and JPEG bytes, duplicate count, local last-frame age, uptime, source session, and sequence number.
- `GET /stream`: `Content-Type: multipart/x-mixed-replace; boundary=cs536frame`. No content encoding or chunked transfer encoding is used by our servers.
- The Python dashboard also offers `GET /frame` (fresh JPEG or HTTP 204) and `GET /` (viewer). The dashboard binds only to localhost and keeps the upstream pairing code out of browser content.

The first multipart boundary immediately follows HTTP headers. Each frame has this form (line endings are CRLF):

```text
--cs536frame
Content-Type: image/jpeg
Content-Length: <exact JPEG byte count>
X-Protocol-Version: 1
X-Source-Session: <UUID or 1-64 alphanumeric/hyphen characters>
X-Frame-Id: <nonnegative signed-64-bit integer>
X-Capture-Mono-Ns: <source local monotonic nanoseconds>
X-Capture-Unix-Ms: <source Unix milliseconds>
X-Width: <upright JPEG width>
X-Height: <upright JPEG height>

<exactly Content-Length JPEG bytes><CRLF>
```

JPEG pixels are rotated at the source when configured; there is no separate display-rotation field. Limits: 4 MiB JPEG, 4096 pixels per dimension, 2048 bytes per header line, 16 KiB aggregate headers, fewer than 40 header lines. Receivers reject duplicate headers, unknown protocol versions, invalid metadata, malformed JPEG envelopes, and truncated frames. The phone additionally checks decoded image bounds before allocating its preview bitmap.

The relay preserves source session, sequence, capture timestamps, dimensions, and JPEG bytes. It assigns no replacement frame IDs. Repeated or out-of-order sequences in the same session are discarded. A camera restart/resume gets a new UUID so sequence 0 can be accepted. Each process stores just the latest frame; each stream client tracks its own last delivered store version.

## Stop, pause, and failure behavior

Pausing the glasses releases their camera and clears the source frame slot. Resuming creates a new camera session. Pausing the phone disconnects its upstream receiver and clears its preview/relay slot; its relay server stays available for subsequent resume.

Frames older than 2.5 seconds since local receipt are not served to new consumers. A stream connection with no new frame for three seconds is closed. Clients use four-second connection/read timeouts and retry with 250 ms to four-second exponential backoff. Successful frames reset backoff. Authentication failures stop retries so the user can correct the code. Android pause/stop invalidates callbacks from older receiver/camera generations.

The Java server has six connection slots and a watchdog that closes sockets with no successful progress for six seconds. The Python test/viewer server has eight slots and four-second socket timeouts. These are initial engineering settings, not assignment-prescribed stall definitions.

## Metrics boundaries

CSV event times are local to the recording device. JPEG byte counts exclude HTTP headers, TCP/IP overhead, retransmissions, and traffic on other interfaces. Frame gaps may reflect capture throttling, an intentionally skipped frame at a relay, or interruption; they do not by themselves measure packet loss. No one-way network latency is claimed without clock calibration. The current implementation is a foreground controlled-network baseline, not a cellular/NAT traversal implementation.
