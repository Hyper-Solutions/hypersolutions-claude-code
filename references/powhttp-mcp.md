# Debugging live requests with powhttp (MCP)

This is the highest-leverage debugging path. powhttp is a local HTTP debugging proxy
that captures your script's real traffic — including **true wire header order** and the
**TLS fingerprint**, neither of which a browser HAR contains. Its MCP server gives
Claude read-only access to that captured traffic, so Claude can inspect exactly what your
HTTP client put on the wire and compare it to a real Chrome request.

Use this whenever a flow is "blocked but the generated payload looks fine" — the fault is
almost always in the request, and powhttp shows the ground truth.

## Prerequisites (one-time)

1. Install powhttp (https://powhttp.com) and start it. Default capture proxy:
   `http://127.0.0.1:8080`.
2. In powhttp, click **"Run MCP server"**. It listens at `http://localhost:8383/mcp`
   (streamable HTTP transport). This plugin registers that server as **`powhttp`**, so its
   tools appear namespaced as `mcp__plugin_hypersolutions_powhttp__find_requests`,
   `…__get_tls_connection`, `…__get_http2_streams`. (If you instead added powhttp as a
   standalone MCP server, the names are `mcp__powhttp__…`.)
3. **Route the failing script through powhttp**: set the script's HTTP/proxy to
   `http://127.0.0.1:8080` (in addition to any upstream scraping proxy — powhttp can
   chain). Run the failing flow so it's captured.

> If the `powhttp` MCP tools aren't available, the server isn't running or isn't
> registered — tell the user to start powhttp and click "Run MCP server". You can still
> analyze a session they export as HAR (powhttp → export) by applying the same
> `references/request-rules.md` rules to the HAR entries (note a HAR lacks the real wire
> header order and TLS fingerprint — powhttp is preferred).

## The three tools

### `find_requests` — query captured traffic
Params: `query` (required) + `include` (required) + optional `limit`.
- `query.sessionId`: use `"active"` for the session currently open in powhttp.
- `query.search`: `{ query, isRegex, caseSensitive, sources? }` — filter by URL/headers/body.
- `query.entryIds`: specific entry IDs, or `"active"` for the selected entry.
- `query.state`: filter by UI state (`selected`, `bookmarked`, `colors`, `strikethrough`).
- `include`: array choosing which fields to return — `request_headers`, `request_body`,
  `response_headers`, `response_body`, `websocket_messages`, `timings`, `fingerprint`,
  `process`. **Omit bodies unless needed** to keep responses small; add `limit`.
- Results carry metadata (URL, method, status, timing) plus `tls.connectionId` and
  `http2.streamId` for drilling deeper, and (with `fingerprint`) the client fingerprint.

### `get_tls_connection` — TLS handshake for a connection
Params: `connectionId` (from a `find_requests` result's `tls.connectionId`) + optional
`limit`. Returns the handshake messages (protocol settings of both sides) — use to inspect
the JA3/JA4-level TLS fingerprint and confirm it matches a real Chrome ClientHello.

### `get_http2_streams` — HTTP/2 frames per stream
Params: `connectionId` + `streams` (list of `{ id, limit? }` where `id` is
`http2.streamId`). Returns HEADERS/DATA/SETTINGS frames — use to read the **actual
pseudo-header order** (`:method :authority :scheme :path` for Chrome) and header frames.

## Recommended debug workflow

1. **Locate the target-site requests.** `find_requests` with `sessionId:"active"`, a
   `search` for the target host (or the antibot request, e.g. `/tl`, `reese84`,
   `geo.captcha-delivery.com`, `sensor_data`), `include:["request_headers"]`, small
   `limit`. Ignore third-party/analytics noise.
2. **Check header order & case.** Read the ordered `request_headers`. Compare against a
   real Chrome order (see `references/tls-and-headers.md`). Look for: alphabetical order,
   wrong case for the HTTP version, `priority` not last (HTTP/2), `cookie` misplaced,
   missing `Host` first (HTTP/1.1), a `Host` header present on HTTP/2.
3. **Check the fingerprint.** Re-query with `include:["fingerprint"]`; then
   `get_tls_connection` on the `tls.connectionId` and `get_http2_streams` on the
   `http2.streamId` to confirm the TLS ClientHello and HTTP/2 pseudo-header order match
   Chrome. A mismatch here is the classic "valid payload, still blocked" cause.
4. **Check the response.** Add `include:["response_headers","response_body"]` on the
   blocked request to read the block/challenge (403 `var dd=`, 428 sec-cpt provider, 429
   ips.js / `{"t":...}`) and any `Accept-CH` / `Set-Cookie` the server sent.
5. **Apply the principles.** Work through `references/request-rules.md` against the
   in-scope requests: header order/case, pseudo-header order, sec-ch-ua exact value,
   duplicate cookies, DevTools cache headers, Accept-CH / client-hint pollution,
   `Sec-Fetch-Storage-Access` incognito artifacts, and Chrome-version policy. For
   per-product flow correctness (Akamai SBSD/sensor, DataDome challenge/cookie/image,
   Kasada), use the product reference files — or, if you can export the capture as a HAR,
   run the `analyze_har` MCP for the full maintained check. Track cross-request state
   (cookie propagation, Accept-CH, flow order).
6. **Map findings to fixes.** Route each finding through `references/debugging.md` and the
   relevant product file. Report the confirmed issues most-severe first, with the exact
   header/value to change.

## Tips

- `sessionId:"active"` is almost always what you want — it's the session the user is
  looking at in powhttp.
- Keep responses small: request only the `include` fields you need, use `limit`, and use
  `search` to narrow to the antibot request instead of pulling the whole session.
- The capture is read-only and local, but request headers/bodies contain live cookies and
  tokens — don't echo secrets back to the user unnecessarily; redact when quoting.
- powhttp minimally alters the TLS fingerprint (unlike Charles), so what you see is close
  to the real wire — but if the user's TLS client is itself behind another proxy, account
  for that.
