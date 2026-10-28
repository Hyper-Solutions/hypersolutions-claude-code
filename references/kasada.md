# Kasada

Endpoints (host `https://kasada.hypersolutions.co`):

| Operation | Endpoint | Go | Python | JS/TS |
|---|---|---|---|---|
| Payload / challenge token (`ct`) | `POST /payload` | `GenerateKasadaPayload` | `generate_kasada_payload` | `generateKasadaPayload` |
| Challenge data / POW (`cd`) | `POST /cd` | `GenerateKasadaPow` | `generate_kasada_pow` | `generateKasadaPow` |
| Vercel BotID (`x-is-human`) | `POST /botid` | `GenerateBotIDHeader` | `generate_botid_header` | `generateBotIDHeader` |

Identify Kasada by a **429** whose HTML references `ips.js`, and by `x-kpsdk-*`
headers/cookies (`tkrm_alpekz_s1.3`, `tkrm_alpekz_s1.3-ssn`). Requires a Chrome UA (Windows recommended; macOS also supported).
Script/endpoint paths use two GUID segments, e.g.
`/149e9513-01fa-4fb0-aad4-566afd725d1b/2d206a39-8ed7-437e-a3be-862e0f06eea3/{ips.js|fp|tl|mfc}`.

> **Compress the request body** (it's large): gzip/br/deflate/zstd + `content-encoding`.
> The SDKs auto-compress bodies > 1000 bytes.

Parse the ips.js path with `ParseScriptPath` (Go `kasada`) /
`parse_kasada_script_path` (Py) / `parseKasadaPath` (JS) — it unescapes `&amp;` → `&`.

---

## Two flows

### Flow 1 — initial block page (429 on homepage)

1. First GET returns **429** HTML referencing
   `<script src="/149e9513-.../ips.js?tkrm_alpekz_s1.3=...&x-kpsdk-im=...">`. Parse the path.
2. **GET `https://site{scriptPath}`** (ips.js); save the JS body.
3. **Generate the payload** via `POST /payload`.
4. **Decode the base64 payload** — the API returns it base64-encoded; you must decode to
   raw bytes before posting. (Go returns already-decoded bytes; Python/JS return the
   base64 string — decode it yourself.)
5. **POST the decoded (binary) payload to `/tl`** with `Content-Type: application/octet-stream`,
   including the API-returned headers `x-kpsdk-im`, `x-kpsdk-ct`, `x-kpsdk-dt`; match
   browser header order.
6. **Parse `/tl`** — expect **200** `{"reload":true}`. Save `x-kpsdk-ct` (token, also in
   cookies), `x-kpsdk-st` (timestamp for POW), and the `set-cookie` values
   (`tkrm_alpekz_s1.3`, `tkrm_alpekz_s1.3-ssn`).
7. **Retry the original request** with the cookies.

### Flow 2 — fingerprint endpoint (`/fp`)

Standard implementation. The browser GETs `/fp?x-kpsdk-v=j-xxx` in the background, which
returns **429** with `ips.js`. The `x-kpsdk-v` value comes from the site's `p.js`: fetch it and
call `POST /version` (below) instead of hardcoding a version, which changes as Kasada ships. Same steps 2–6, but **set the referer to the `/fp` URL**
on the ips.js and `/tl` requests. Then protected endpoints require:
- **Kasada cookies** (always).
- **`x-kpsdk-ct`** header (if the browser sends it) — from the `/tl` response, or the
  last value returned by a protected endpoint.
- **`x-kpsdk-cd`** header (if the browser sends it) — a POW that **must be freshly
  generated for every single request. Reusing POW values will cause failures.**

**Optional `/mfc` step:** if the browser GETs `/mfc`, do it after `/tl` and before
protected requests (include Kasada cookies). It sends `x-kpsdk-h:01` and `x-kpsdk-v`, and
you read back `x-kpsdk-fc` (feature config — needed as the `fc` POW input on `/mfc`
sites) and `x-kpsdk-h`. If there's no `/mfc`, omit the `fc` param when generating POW.

Re-solve the whole flow when cookies expire or you get a **429** on a protected endpoint.
Refresh tokens proactively.

---

## Input / output fields

### `KasadaPayloadInput` → `POST /payload`

`userAgent` (Chrome Windows/macOS), `ipsLink` (ips.js link parsed from the 429 page), `script`
(ips.js body), `acceptLanguage`, `ip` (optional), `strict` (optional bool, default false),
`dv` (optional, iOS app flow only: the `x-kpsdk-dv` you send to the site, see
[x-kpsdk-dv](#mobile-x-kpsdk-dv)).
(JS ctor: `new KasadaPayloadInput(userAgent, ipsLink, script, ip, acceptLanguage, strict?, dv?)`.)

Output = a `KasadaPayloadResult`: `payload`, `headers` (`KasadaHeaders`: `x-kpsdk-ct`,
`x-kpsdk-dt`, `x-kpsdk-v`, `x-kpsdk-r`, `x-kpsdk-dv`, `x-kpsdk-h`, `x-kpsdk-fc`,
`x-kpsdk-im`) and the client hints (API key `clientHints`; SDK `ClientHints` /
`client_hints` / `clientHints`). Keep the two apart: the `x-kpsdk-*` headers go on every
`/tl` request, the client hints only when the site asks for them (`Accept-CH`; see
`references/api-reference.md`).

**`strict`:** Kasada changes the signals `ips.js` collects. When the script has a signal the
API cannot identify yet, the API normally fills that slot with the script's own literal and
returns the payload. With `strict: true` it refuses instead: HTTP `500`,
`{"error":"Unidentified signals in script; refusing payload because strict was set"}`.
Use it when you would rather retry later or fall back than post a payload with an
unreadable slot. SDKs only send it when set: Go v4.0.0 `Strict`, Python 4.0.0 `strict=True`,
JS 5.0.0 last ctor arg.

### `KasadaVersionInput` → `POST /version`

| Field (Go) | Python | Meaning |
|---|---|---|
| `PageUrl` | `page_url` | The page that loaded `p.js` (domain whitelist) |
| `Script` | `script` | The `p.js` body, fetched with the same client and headers |

Returns `version`, the `x-kpsdk-v` value (e.g. `j-1.2.797`): send it verbatim on the `/fp`
request and in the `x-kpsdk-v` header. Not counted as usage. An ips.js (or anything that is not
p.js) is a 400. JS: `getKasadaVersion(session, new KasadaVersionInput(pageUrl, script))`.

### `KasadaPowInput` → `POST /cd`

| Field (Go) | Python | Meaning |
|---|---|---|
| `St` (int) | `st` | The `x-kpsdk-st` from the `/tl` response |
| `Ct` | `ct` | The `x-kpsdk-ct` from `/tl` |
| `Fc` | `fc` (default `""`) | The `x-kpsdk-fc` from `/mfc` (omit if no `/mfc`) |
| `Domain` | `domain` | Target domain |
| `Script` | *(n/a in Py input)* | ips.js body (Go/JS) |
| `WorkTime` (`*int`) | `work_time` (default `None`) | Optional — pre-generate POW strings |

Returns a result whose `payload` is the `x-kpsdk-cd` value. (JS ctor: `new KasadaPowInput(st, ct, domain, fc?, workTime?)`.)

> **Mobile User-Agent:** when the payload was generated with a **mobile** UA, send
> **only `st`** on `/cd` — omit `ct`, `domain`, `fc`, and `script`. Sending those
> desktop-only fields with a mobile UA will produce an invalid POW. `work_time` may
> still be passed optionally. (Desktop UAs keep sending the full field set above.)

### `BotIDHeaderInput` → `POST /botid`

`script` (the BotID `c.js` body), `userAgent`, `ip`, `acceptLanguage`. Returns a result whose
`payload` is the `x-is-human` value. (JS ctor: `new BotIDHeaderInput(script, userAgent, ip, acceptLanguage)`.)

---

## Vercel BotID (`x-is-human`)

Kasada-backed; identify by an `x-is-human` header on protected requests.

1. **GET the BotID script `c.js`**, e.g.
   `https://site/149e9513-.../a-4-a/c.js?i=0&v=3&h=www.example.com`; save the JS body.
2. **Generate** via `POST /botid`.
3. **Send** the returned token as the `x-is-human` header on protected requests.

Re-generate on a `429` or when the proxy IP changes.

---

## Supported user agents

Desktop (recommended = Windows Chrome; macOS Chrome also supported):
```
Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{VER}.0.0.0 Safari/537.36
Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{VER}.0.0.0 Safari/537.36
```

Kasada also supports specific **mobile app** UAs (native iOS/Android app user-agents, e.g.
`<AppName>/X.X.X iOS/X.X`, `<AppName>/CFNetwork/Darwin`, `<AppName> vXX.XX.0 (XX), iOS X.X,
iPhoneXX,X`). If you're integrating a mobile app flow, ask Hyper Solutions whether your
app's UA is supported.

### Mobile x-kpsdk-dv

On iOS the Kasada SDK sends an `x-kpsdk-dv` header from the very first request, before the
API is called, so the client builds it. It is base64 of a JSON object XORed with a key fixed
in the Kasada SDK:
```
{"osVersion":"18.0.1","hardwareId":"iPhone13,2","appId":"com.example.app","appVersion":"9.15.0"}
```
`hardwareId` is the model identifier from `utsname.machine` (`iPhone13,2` is an iPhone 12),
not the marketing name. `appId` and `appVersion` are the same bundle id and app version the
hashed user-agent below is built from; from Kasada SDK `i-2.x` (the `x-kpsdk-v` value) they
are required, and a header without them is rejected.

Generate it locally with `GenerateDV(osVersion, hardwareID, appID, appVersion)` (Go
`kasada`) / `generate_kasada_dv(os_version, hardware_id, app_id, app_version)` (Py) /
`generateKasadaDv({ osVersion, hardwareId, bundleId, appVersion })` (JS). Example values
above → `QkZWEmcDRUBEDloaAg8FDhpTAwhEGxFFWRFcQAVCVHFXFAlBUDRRDl8DBgABUxYUGkxERn0HDwNEVFxAFgZAVglAXV0dV0MTG0gbAEEWYVZfEl1XVg8OFA1NHAxIBxFQ`.
If you captured the header from the app you emulate, send that exact value instead.

Then send the same value as `dv` on `POST /payload`: the API generates the payload on a real
iPhone with that model's screen and iOS version, so the payload and the header agree.
Without `dv` it picks a device from the iOS version in the user-agent (any recent iPhone for
the hashed form). A `dv` that does not decode is a 400 `invalid dv`. Build the user-agent and
the `dv` from the same values.

### Mobile app user-agent generation

On the native mobile flow the `user-agent` is **not a readable UA string**. The Kasada 2.x mobile SDK sends a 32-char hex **MD5** of the device and app identity:
```
<osVersion> / <bundleId> <appVersion>
```
` / ` separates the OS version and bundle id; a single space precedes the app version.

| Component | iOS | Android |
|---|---|---|
| `osVersion` | `UIDevice.systemVersion` (e.g. `18.0.1`) | `Build.VERSION.SDK_INT` (e.g. `34`) |
| `bundleId` | `CFBundleIdentifier` (e.g. `com.example.app`) | package name |
| `appVersion` | `CFBundleShortVersionString` (e.g. `9.15.0`) | `versionName` |

Generate it locally (no API call) with `GenerateUserAgent` (Go `kasada`) / `generate_kasada_user_agent` (Py) / `generateKasadaUserAgent` (JS). It is pure device+app identity with no per-request nonce, so it is stable for a given triple. Example: `18.0.1 / com.example.app 9.15.0` → `7016adc4ba8d433533954ebad33be424`. Available since hyper-sdk-go v3.1.0, hyper-sdk-js 4.1.0, and hyper_sdk 3.1.0 (and in Go v4,
Python 4.0.0, JS 5.0.0).

> Use the real OS version, bundle id and app version for the build you emulate. One different byte in any field changes the whole hash, and a UA that does not match the rest of your mobile fingerprint can get the request flagged.

---

## Kasada status-code summary

| Code | Meaning | Action |
|---|---|---|
| `429` | Challenge (homepage in Flow 1, `/fp` in Flow 2, or a protected endpoint when tokens expire) | Run/re-run the payload → `/tl` → POW flow |
| API `500` "refusing payload because strict was set" | `strict` on and the script has an unidentified signal | Retry later or without `strict` |
| `200` `{"reload":true}` on `/tl` | Challenge accepted | Save `x-kpsdk-ct`/`x-kpsdk-st` + cookies, retry original |

**Final headers on protected requests:** Kasada cookies + `x-kpsdk-ct` + `x-kpsdk-cd`
(fresh POW every request) + `x-kpsdk-h`/`x-kpsdk-v` where the browser sends them.
