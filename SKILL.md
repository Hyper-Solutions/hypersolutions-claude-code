---
name: hypersolutions
description: >-
  Integrate and debug the Hyper Solutions API for bypassing anti-bot systems —
  Akamai Bot Manager, Incapsula/Imperva, DataDome, and Kasada.
  Use when working with the hyper-sdk (Go), hyper-sdk-py (Python), or hyper-sdk-js
  (JavaScript/TypeScript) SDKs, or calling the *.hypersolutions.co API directly;
  when generating sensor data, _abck / reese84 / ___utmvc / datadome cookies,
  Kasada x-kpsdk-* tokens, sec-cpt (428) or SBSD (429) payloads, DataDome
  interstitial/slider/tags, or Vercel BotID x-is-human headers; and when
  debugging blocks, challenges, 403/428/429 responses, TLS fingerprinting, or
  header-order problems in request-based scraping. Triggers on: Hyper Solutions,
  hypersolutions, hyper-sdk, Akamai sensor, _abck, sec-cpt, sbsd, Incapsula,
  reese84, utmvc, DataDome, Kasada, kpsdk, anti-bot bypass,
  powhttp, HAR analysis, captured-request debugging, header order.
---

# Hyper Solutions API Integration

## What this service does (mental model)

Hyper Solutions is a **payload-generation API**. It does **not** make requests to the
target site for you. It takes inputs you collect from the protected site (script
contents, cookies, UUIDs, IP, User-Agent) and returns the **sensor data / cookie /
token** a real browser would produce. **Your code** is responsible for all the actual
HTTP traffic to the target — with a browser-grade TLS client and correct header order.

```
┌────────────┐   1. GET page / script      ┌──────────────┐
│ Your code  │ ──────────────────────────► │ Target site  │
│ (TLS       │ ◄────────────────────────── │ (Akamai/DD/…)│
│  client)   │   2. HTML, cookies, script   └──────────────┘
│            │
│            │   3. inputs (script, cookies, ip, ua)   ┌────────────────────┐
│            │ ──────────────────────────────────────► │ *.hypersolutions.co │
│            │ ◄────────────────────────────────────── │ (this API)          │
│            │   4. generated payload / token           └────────────────────┘
│            │
│            │   5. POST payload back to target ─────►  Target site → valid cookie
└────────────┘
```

If a request is failing, the cause is almost always in **step 1/5 (your TLS client,
header order, cookies, or IP)**, not in the generated payload. See
`references/debugging.md` first.

## Non-negotiable requirements

These apply to **every** product. Standard HTTP libraries (`requests`, `axios`,
`net/http`, `fetch`) will be blocked — they have non-browser TLS fingerprints.

1. **Browser-grade TLS client** with a Chrome fingerprint (e.g. `tls-client`,
   `azuretls-client`, `rnet`/`wreq`, `tlsclientwrapper`). Recommended profile: the
   **latest Chrome profile your client offers**, with **HTTP/3 disabled** (most proxies
   don't support it yet) and **random TLS extension order enabled**.
2. **Exact browser header order**, including HTTP/2 pseudo-header order. This is a top
   fingerprinting signal and DevTools does **not** show the real order.
3. **Session consistency**: the same User-Agent, TLS fingerprint, IP, and header order
   for the entire flow. A proper cookie jar. Consistent client-hint headers.
4. **Sticky/session proxies, never rotating** — the IP you send to the API must match
   the IP the target site sees. Pass your outbound IP as the `ip` input (get it from
   `GET https://ip.hypersolutions.co/ip`).
5. **Match Chrome versions across the board**: UA version, `sec-ch-ua`, and
   `sec-ch-ua-platform` must agree. Mismatched versions flag automation.

Full detail: `references/tls-and-headers.md`.

## Authentication

Every API request needs the `x-api-key` header (get a key at
https://hypersolutions.co/keys). Optionally add JWT signing (`x-signature`) for
client-side use, or organization headers (`x-app-key` + `x-app-signature`). The SDKs
handle all of this for you. Full detail + code: `references/authentication.md`.

## Install & construct a session

| Language | Package | Construct |
|---|---|---|
| Go | `github.com/Hyper-Solutions/hyper-sdk-go/v2` | `hyper.NewSession("api-key")` |
| Python | `hyper-sdk` (PyPI) | `Session("api-key")` / `SessionAsync("api-key")` |
| JS/TS | `hyper-sdk-js` (npm) | `new Session("api-key")` |

```go
// Go
session := hyper.NewSession("your-api-key").
    WithJwtKey("your-jwt-key").      // optional
    WithClient(customHTTPClient)     // optional
```
```python
# Python (sync) — also SessionAsync with the same signature, methods are awaitable
from hyper_sdk import Session, SensorInput
session = Session("your-api-key", jwt_key=None, app_key=None, app_secret=None)
```
```typescript
// JS/TS
import { Session } from 'hyper-sdk-js';
const session = new Session("your-api-key", jwtKey?, appKey?, appSecret?, options?);
```

- **Go**: product methods are on the `Session` (e.g. `session.GenerateSensorData(ctx, input)`), take a `context.Context` first, and a pointer to an input struct.
- **Python**: product methods are on the session (e.g. `session.generate_sensor_data(input)`); input classes use keyword args.
- **JS/TS**: product operations are **free functions** taking the session as the first arg (e.g. `generateSensorData(session, input)`); input classes use **positional** constructor args (arg order sometimes differs from field order — see `references/api-reference.md`).

No language SDK? Call the REST API directly — see `references/api-reference.md`.

## Which product am I dealing with? (routing)

Identify the anti-bot system, then open the matching reference file.

| System | How to identify it | Reference |
|---|---|---|
| **Akamai** Bot Manager | `_abck` and `bm_sz` cookies; a `<script src="/xxxx/yyyy/...">` dynamic path near end of body. `428` = sec-cpt challenge; `429 {"t":...}` = SBSD block | `references/akamai.md` |
| **Incapsula/Imperva** | Cookie named `reese84` or an `x-d-token` header → reese84. A script like `/_Incapsula_Resource?SWJIYLWA=...` → utmvc. "Pardon Our Interruption" page → reese84 dynamic | `references/incapsula.md` |
| **DataDome** | `403` with a body containing `var dd={...}`. `i.js` referenced → interstitial; `c.js` → slider. `datadome` cookie | `references/datadome.md` |
| **Kasada** | `429` with HTML referencing `ips.js`; `x-kpsdk-*` headers/cookies (`tkrm_alpekz_*`). `x-is-human` header → Vercel BotID | `references/kasada.md` |

## Cross-cutting concerns

- **IP & proxies** — sticky proxies; `GET /ip`; consequences of rotating IPs → covered in `references/tls-and-headers.md`.
- **User agents & Chrome version** — Windows Chrome recommended (macOS Chrome also supported); when/how to bump the version; keep `sec-ch-ua` in sync → `references/tls-and-headers.md`.
- **Compression** — enable it in **both** directions (request payload + response) on basically every call. Pick the codec by language support: **zstd** where it's well-supported (Go), **gzip** otherwise (Python, JS/TS). SDKs auto-compress payloads > 1000 bytes and their defaults already follow this (Go → zstd; Python/JS → gzip) → `references/api-reference.md`.
- **Usage/quota** — `GET https://api.hypersolutions.co/usage` (personal-org API) for remaining quota.
- **Response `headers` object** — most generate endpoints return a `headers` object of client hints (`sec-ch-ua-full-version-list`, `sec-ch-ua-platform`, etc.). **Replay these on the target site; never hardcode them.**

## Debugging

When an integration is failing (still blocked, challenge won't clear, 403/428/429
persists), the fault is almost always in the **request** (TLS fingerprint, header order,
cookies, IP), not in the generated payload. The most common root causes, in order:

1. TLS fingerprint / header order not actually matching a real browser.
2. IP mismatch (rotating proxy, or API `ip` ≠ target-facing IP).
3. Cookie-jar bugs (missing, duplicated, or wrong-domain cookies).
4. `sec-ch-ua` / UA / platform version mismatch, or hardcoded client hints from a polluted
   browser capture (`Accept-CH` / `Sec-Fetch-Storage-Access` artifacts).
5. Reusing a value that must be fresh (Kasada POW, Akamai context, tokens past renewal).

**Four debugging tools, best first:**

1. **Live capture with powhttp (MCP)** — the ground truth. If the powhttp MCP tools
   (`find_requests`, `get_tls_connection`, `get_http2_streams` — namespaced
   `mcp__plugin_hypersolutions_powhttp__*` when provided by this plugin) are available,
   route the failing script through powhttp, run it, and inspect the **real wire header
   order and TLS fingerprint** — things a HAR can't show. Workflow:
   `references/powhttp-mcp.md`.
2. **HAR analysis (MCP)** — when you have a **HAR** but no live powhttp capture (e.g. a
   customer sent one), pass its contents to `analyze_har` (namespaced
   `mcp__plugin_hypersolutions_har-analyzer__analyze_har`). It returns structured findings
   (severity, category, fix) plus the detected product. **This rule set is kept up to date
   — prefer it over the static `references/request-rules.md`.** Its findings are reliable
   when the HAR was recorded by a debugger that preserves the real wire header order (e.g.
   a **powhttp** export); a HAR from Charles or DevTools normalizes header order, so trust
   its order/pseudo-header findings less. A HAR never carries the TLS fingerprint, so a
   clean result doesn't rule that out — escalate to powhttp. Workflow:
   `references/har-analyzer-mcp.md`.
3. **Request-fingerprinting principles** — `references/request-rules.md` is a concise
   principles reference for the generic fingerprint concepts (header order/case,
   pseudo-header order, sec-ch-ua GREASE, cookies, client-hint/`Accept-CH` pollution,
   Chrome-version policy, header-order shapes). Use it to **analyze a powhttp capture**
   (the HAR MCP can't read powhttp's live TLS / HTTP/2 data), to reason by hand when no MCP
   is available, or to write correct requests up front. Per-product flow checks live in the
   HAR analysis MCP and the product references. It ships a runnable helper,
   `scripts/sec_ch_ua.py`, to compute the exact expected `sec-ch-ua` for any Chrome version
   — use it instead of eyeballing.
4. **Symptom → cause → fix** — `references/debugging.md`, per product and cross-cutting.

## Getting help / escalating to Hyper Solutions

- Working examples for every product × language: the `hypersolutions-examples` repo
  (https://github.com/Hyper-Solutions/hypersolutions-examples). Distilled skeletons are
  in `references/api-reference.md`.
- For support, Hyper Solutions asks for a **HAR captured with powhttp** (not Charles —
  powhttp preserves the real wire header order; see `references/tls-and-headers.md`). HAR
  files contain cookies/tokens — sanitize sensitive data before sharing. Discord:
  `discord.gg/akamai`. You can pre-screen the HAR yourself with the `analyze_har` MCP tool
  (`references/har-analyzer-mcp.md`) before escalating.

## Reference index

| File | Contents |
|---|---|
| `references/authentication.md` | `x-api-key`, JWT `x-signature`, organization headers, code for all 3 languages |
| `references/tls-and-headers.md` | TLS fingerprinting, header order, pseudo-header order, common pitfalls, IP/proxy rules, Chrome-version policy, capture tooling |
| `references/akamai.md` | Sensor flow (`_abck`), sec-cpt 428 (crypto/behavioral/adaptive), SBSD 429 (passive/hard/429), pixel, cookie-validity helpers |
| `references/incapsula.md` | reese84, reese84 dynamic ("Pardon Our Interruption" + PoW), utmvc, captcha block |
| `references/datadome.md` | interstitial, slider, tags, the `dd` object, `t:'bv'` hard block |
| `references/kasada.md` | Flow 1 (block page) & Flow 2 (`/fp`), `/payload` `/cd` `/botid`, POW freshness, `/mfc`, Vercel BotID, supported UAs |
| `references/api-reference.md` | Every endpoint, every input/output field, per-SDK signatures, raw-HTTP contract, compression, response envelope |
| `references/powhttp-mcp.md` | Live request-capture debugging via the powhttp MCP (find_requests / get_tls_connection / get_http2_streams) |
| `references/har-analyzer-mcp.md` | Automated HAR fingerprint analysis via the har-analyzer MCP (`analyze_har`) |
| `references/request-rules.md` | Fingerprint principles for reasoning over a powhttp/live capture and writing correct requests: generic rules, client-hints/Accept-CH, Chrome version, header-order shapes, sec-ch-ua GREASE (per-product flow → the HAR MCP + product files) |
| `references/debugging.md` | Symptom → cause → fix, per product and cross-cutting |
