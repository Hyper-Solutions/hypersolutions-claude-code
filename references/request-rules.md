# Request Fingerprinting — Principles

Concise principles for reasoning about a **live capture** (powhttp) or a request you're
**writing**, and for understanding a finding by hand.

> For a **HAR**, use the **har-analyzer MCP** (`references/har-analyzer-mcp.md`) — it runs
> the full, maintained rule set server-side and is the source of truth. This file is the
> lighter-weight companion for what the MCP can't cover: analyzing powhttp's live wire data
> (header order, TLS, HTTP/2 frames), reasoning when no MCP/HAR is available, and writing
> correct requests up front.

## How to analyze a capture

1. **Prefer powhttp** (`references/powhttp-mcp.md`): `find_requests` gives the real wire
   header order, `get_http2_streams` the pseudo-header order, `get_tls_connection` /
   `fingerprint` the TLS fingerprint — none of which a browser HAR contains.
2. **Scope to the target site + anti-bot domains.** Skip analytics/ads/CDN/telemetry noise.
3. **Report confirmed-first** with the exact header/value/URL and the precise fix.

## Generic request principles

How a real Chrome differs from a stock HTTP library. Check these on every in-scope request:

- **Header case:** all-lowercase on HTTP/2; Title-Case on HTTP/1.1.
- **Pseudo-header order (HTTP/2):** Chrome = `:method :authority :scheme :path` (Firefox and
  Safari differ — see below). Stable per browser and a strong signal — only visible via
  powhttp, never a HAR.
- **No alphabetical header order** — the classic `requests`/`axios` tell. Configure a
  browser header order; don't let the client sort.
- **Positions (Chrome):** HTTP/1.1 → `Host` first (then `Connection, Content-Length` on a
  POST); HTTP/2 → **no** `Host` header (`:authority` replaces it) and `priority` **last**;
  cookies grouped at the end, before `priority`.
- **`cookie` must be in the header order whenever `priority` is** — list it explicitly
  right before `priority`, even with no cookies yet. Most TLS clients auto-append `cookie`
  last, so omitting it yields `…, priority, cookie` (wrong) instead of `…, cookie,
  priority`. Any order ending in `priority` must have `cookie` immediately before it.
- **No duplicate `content-length`** — never set it manually; let the client compute it.
- **Clean cookie jar** — the same cookie *name* twice with *different* values is a jar bug.
- **`sec-ch-ua`** must (a) match the UA's Chrome major version and (b) be the exact GREASE
  value for it. Don't eyeball it — `python scripts/sec_ch_ua.py <version>` (or
  `--check <version> '<captured value>'`). A grease brand that matches a *different* version
  with the version numbers bumped up is a hardcoded/stale value — the brand, its grease
  version, and the brand order all change per Chrome version, so bumping only the numbers
  produces an impossible combination.
- **`sec-ch-ua-platform`** quoted and matching the UA OS (`"Windows"` / `"macOS"`).
- **`accept-encoding`** for Chrome = `gzip, deflate, br, zstd`.
- **Valid `accept-language`** (e.g. `en-US,en;q=0.9`) and a well-formed `origin`
  (exactly `scheme://host[:port]`, no trailing slash/path/query).
- **No DevTools "Disable cache" artifacts** (`cache-control: no-cache` **and** `pragma:
  no-cache` together).

**Don't over-flag normal header order.** Chrome sends a *different* order for navigation vs
fetch/XHR vs subresource, and anti-bot endpoints have their own. Never call a request wrong
just because its order differs from another in the same capture. Only flag: alphabetical
order, wrong **pseudo-header** order (that one *is* stable per browser), the position rules
above, or a grossly non-browser pattern.

**Cookie transport differs by HTTP version — not a bug.** On HTTP/2 Chrome sends **each
cookie as its own `cookie` header** (correct — HPACK, RFC 9113 §8.2.3). On HTTP/1.1 they
coalesce into one `Cookie: a=b; c=d`. Multiple `cookie` headers on h2 are fine; the
anomalies are the inverse (all cookies in one header on h2, or multiple `Cookie` on h1.1).

## Client hints & Accept-CH

High-entropy client hints (`sec-ch-ua-arch`, `-full-version-list`, `-model`,
`-platform-version`, `-bitness`, `-wow64`, `-form-factors`, `sec-ch-device-memory`) must
appear **only after** the origin requested them via an `Accept-CH` response header. Sending
them unsolicited — copied from a polluted or incognito browser capture — contradicts the
generated sensor payload and is a top **DataDome**-block cause. Low-entropy hints
(`sec-ch-ua`, `-mobile`, `-platform`) are fine by default. Related: `sec-fetch-storage-access:
none` to `geo.captcha-delivery.com` is usually an incognito/Guest recording artifact (should
be `active`). Governing principle: **the headers and the JS-generated sensor payload must
describe the same browser.**

## Chrome version

Track against the Chromium release schedule. Don't run a UA ≥2 milestones behind current
stable, or ahead of it (a not-yet-released version is an obvious tell; a day-one bump is
risky — wait a few days after a stable release). When you change the version, change **all
of**: UA version, `sec-ch-ua`, and `sec-ch-ua-platform` together.

## Which anti-bot is this?

Identify the product per request/response, then apply its product reference.

- **Akamai** — cookies `_abck`, `bm_sz`, `bm_so`, `sbsd_o`, `sbsd_c`, `bm_sc`, `bm_sv` → `references/akamai.md`
- **Incapsula/Imperva** — cookie `reese84`; prefixes `incap_ses_`, `visid_incap_`, `incap_sh_`; header `x-iinfo` → `references/incapsula.md`
- **DataDome** — requests to `*.captcha-delivery.com`; cookie `datadome`; headers `x-datadome*`, `x-dd-*` → `references/datadome.md`
- **Kasada** — any `x-kpsdk-*` header in request or response → `references/kasada.md`

**Per-product flow correctness** — Akamai SBSD/sensor submission, DataDome challenge
sequencing and `datadome`-cookie freshness, Kasada POW/token freshness — is checked by the
**har-analyzer MCP** on a HAR, and documented for writing integrations in each product
reference above. (Quick reminders: Akamai — stop sensors once `_abck` contains `~0~`;
DataDome — solve the challenge type the block actually is, image requests are cookieless;
Kasada — `x-kpsdk-cd` POW must be freshly generated per request.)

For TLS fingerprint specifics, see `references/tls-and-headers.md`.
