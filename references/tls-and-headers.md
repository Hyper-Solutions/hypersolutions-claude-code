# TLS Fingerprinting, Header Order, IP & User-Agents

This is the foundation everything else sits on. **Most integration failures are here,
not in the generated payload.** If the API returns a valid payload but the target still
blocks you, re-read this file.

## Why standard HTTP clients fail

`requests`, `httpx`, `axios`, `node-fetch`, Go `net/http`, etc. produce TLS handshakes
and header orderings that don't match any real browser. Anti-bot systems fingerprint
both. You **must** use a browser-mimicking TLS client.

### Recommended TLS clients

| Language | Client | Notes |
|---|---|---|
| Go | `github.com/bogdanfinn/tls-client` (+ `bogdanfinn/fhttp`) | Profile `profiles.Chrome_133`, `WithRandomTLSExtensionOrder()` |
| Go | `github.com/Noooste/azuretls-client` (+ `Noooste/fhttp`) | `session.GetClientHelloSpec = azuretls.GetLastChromeVersion` |
| Python | `tls-client` (Nintendocustom fork) | `client_identifier="chrome_133"`, `random_tls_extension_order=True` |
| Python | `rnet` / `wreq` (async) | `Emulation.Chrome143`; note the examples' Akamai async uses `wreq` |
| Node | `tlsclientwrapper` | `tlsClientIdentifier: 'chrome_133'`, `randomTlsExtensionOrder: true` |

Recommended baseline config across all clients:
- **Profile: the latest Chrome profile your client offers** (e.g. `tls-client`'s newest
  `chrome_*` identifier, `rnet`/`wreq`'s newest `Emulation.Chrome*`). The TLS profile may
  lag the UA version you run — see the Chrome-version section.
- **Random TLS extension order: enabled.**
- **Redirects disabled** (challenge redirects must be observed, not auto-followed).
- **Cookie jar enabled.**
- **HTTP/3 disabled** — most proxies don't support it yet.

## Header order

Header order (and HTTP/2 **pseudo-header** order) is one of the strongest bot signals.
Both HTTP/1.1 and HTTP/2 preserve the order you send.

### Pseudo-header order by browser

| Browser | Order |
|---|---|
| Chrome | `:method`, `:authority`, `:scheme`, `:path` |
| Firefox | `:method`, `:path`, `:authority`, `:scheme` |
| Safari | `:method`, `:scheme`, `:path`, `:authority` |

In Go's fhttp this is `http.PHeaderOrderKey`; regular header order is `http.HeaderOrderKey`.

### A real captured Chrome HTTP/2 order (example)

```
:method, :authority, :scheme, :path,
sec-ch-ua, sec-ch-ua-mobile, sec-ch-ua-platform,
upgrade-insecure-requests, user-agent, accept,
sec-fetch-site, sec-fetch-mode, sec-fetch-user, sec-fetch-dest,
accept-encoding, accept-language, priority
```

You must capture the **actual** order for the specific request you're replaying — it
differs between navigation requests, XHR/fetch, subresources (script/image), and the
anti-bot's own endpoints. **A different order on a different request is normal, not a
bug** — don't "fix" one request to match another. The one thing that *is* stable per
browser is the **pseudo-header** order (Chrome `:method :authority :scheme :path`).

**Cookies by HTTP version:** on **HTTP/2** Chrome sends **each cookie as its own `cookie`
header** (multiple `cookie` lines — this is correct). On **HTTP/1.1** they're coalesced
into one `Cookie: a=b; c=d` header. Multiple `cookie` headers on h2 are fine; don't flag
them.

### Common header-order pitfalls (these cause silent blocks)

1. **Header case**: HTTP/1.1 uses `Title-Case`; HTTP/2 uses `lowercase`. Sending the
   wrong case is a fingerprint mismatch.
2. **Never manually set `Content-Length`** — the client computes it. Setting it manually
   sends it twice and fails the request.
3. **`sec-ch-ua` must match the UA's Chrome version** (see below). This is a frequent bug.
4. **If `priority` is in your header order, you MUST list `cookie` explicitly right
   before it** — even on the first request when you have no cookies yet. Most TLS clients
   **append** the `cookie` header at the very end automatically, so if you leave `cookie`
   out of the order you get `…, priority, cookie` instead of Chrome's intended
   `…, cookie, priority` — `priority` is no longer last, which fingerprints as automated.
   Rule of thumb: **any header-order array that ends in `priority` must contain `cookie`
   immediately before it.**
   ```
   # WRONG — cookie omitted; client appends it → priority no longer last
   …, accept-encoding, accept-language, priority        →  …, priority, cookie
   # RIGHT — cookie placed before priority
   …, accept-encoding, accept-language, cookie, priority
   ```
5. **No duplicate cookies** — the same cookie name with two values in one request (a
   broken cookie jar) is a very common, hard-to-spot bug.
6. **Never hardcode `sec-ch-ua-full-version-list`** (especially for DataDome) — the API
   returns the correct value in its response `headers` object; replay that.

### Capturing the real order — tooling

DevTools **does not** show wire header order — never trust it. Use a proxy:

- **Charles Web Proxy** (https://www.charlesproxy.com/download/): trust its root cert
  into "Trusted Root Certification Authorities", enable SSL Proxying with a wildcard
  host include, route traffic through `http://127.0.0.1:8888`. Caveat: Charles alters
  the TLS fingerprint, so some sites block it; its "External Proxy" feature also moves
  `Content-Length` to the bottom, corrupting the order you capture.
- **powhttp** (https://powhttp.com, default `http://127.0.0.1:8080`): shows exact header
  order without significantly altering the TLS fingerprint. Preferred for order capture.
- When recording, **turn off DevTools "Disable cache"** — it injects two non-browser
  headers.
- Diff your client's order against the captured order with https://diffchecker.com.

## IP and proxies

Most endpoints require the outbound IP as the `ip` input. **The IP you send to the API
must equal the IP the target site sees on your requests.**

- **Use sticky/session proxies. Never rotating proxies.** Rotating proxies hand out a
  new IP per CONNECT, so the IP `/ip` reports won't match what the target observes, and
  the generated sensor becomes invalid.
- Get your outbound IP with `GET https://ip.hypersolutions.co/ip` (route it through the
  same proxy you use for the target).
- No proxy? Use your machine's public IPv4.
- Datacenter / known-proxy IPs are themselves a detection signal for some sites.

## User agents & Chrome version

The API generates data based on the **most recent stable Chrome on Windows**. Match it.

- **Windows Chrome is recommended** (macOS is also supported). One UA for all requests
  is fine.
  ```
  Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/XXX.0.0.0 Safari/537.36
  Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/XXX.0.0.0 Safari/537.36
  ```
- **Keep versions in lockstep.** When you bump the Chrome version, update **all** of:
  UA version, `sec-ch-ua` (e.g. `"Chromium";v="141", "Not(A:Brand";v="8", "Google Chrome";v="141"`),
  and `sec-ch-ua-platform` (`"Windows"` / `"macOS"`). Mismatched versions strongly
  indicate automation. Don't switch platforms mid-session.
- **Timing**: track the schedule at https://chromiumdash.appspot.com/schedule (Chrome
  ships ~every 4 weeks). **Wait 3–7 days after a stable release before updating** your UA.
- **TLS-profile fallback**: if your TLS library doesn't yet have the newest Chrome
  profile, you may keep a recent profile (e.g. Chrome 139/140) while sending a newer UA
  (e.g. 141). Treat this as a temporary fallback, not a steady state.

Sources for the latest Chrome version:
- https://versionhistory.googleapis.com/v1/chrome/platforms/win/channels/stable/versions/
- https://chromiumdash.appspot.com/schedule

## Canonical fingerprint constants (from the examples repo)

The examples use a consistent set you can copy as a starting point:

```
UserAgent       = Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36
sec-ch-ua       = "Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"
sec-ch-ua-platform = "Windows"
sec-ch-ua-mobile   = ?0
TLS profile     = latest available per client (e.g. tls-client chrome_133 / rnet Chrome143)
```
(Update the version numbers per the policy above; use the newest profile your client
ships, which may still lag the UA version.)
