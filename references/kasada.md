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
returns **429** with `ips.js`. Same steps 2–6, but **set the referer to the `/fp` URL**
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
(ips.js body), `acceptLanguage`, `ip` (optional).

Output = `(payload, headers)`. The `headers` object (`KasadaHeaders`):
`x-kpsdk-ct`, `x-kpsdk-dt`, `x-kpsdk-v`, `x-kpsdk-r`, `x-kpsdk-dv`, `x-kpsdk-h`,
`x-kpsdk-fc`, `x-kpsdk-im`.

### `KasadaPowInput` → `POST /cd`

| Field (Go) | Python | Meaning |
|---|---|---|
| `St` (int) | `st` | The `x-kpsdk-st` from the `/tl` response |
| `Ct` | `ct` | The `x-kpsdk-ct` from `/tl` |
| `Fc` | `fc` (default `""`) | The `x-kpsdk-fc` from `/mfc` (omit if no `/mfc`) |
| `Domain` | `domain` | Target domain |
| `Script` | *(n/a in Py input)* | ips.js body (Go/JS) |
| `WorkTime` (`*int`) | `work_time` (default `None`) | Optional — pre-generate POW strings |

Returns the `x-kpsdk-cd` value. (JS ctor: `new KasadaPowInput(st, ct, domain, fc?, workTime?)`.)

> **Mobile User-Agent:** when the payload was generated with a **mobile** UA, send
> **only `st`** on `/cd` — omit `ct`, `domain`, `fc`, and `script`. Sending those
> desktop-only fields with a mobile UA will produce an invalid POW. `work_time` may
> still be passed optionally. (Desktop UAs keep sending the full field set above.)

### `BotIDHeaderInput` → `POST /botid`

`script` (the BotID `c.js` body), `userAgent`, `ip`, `acceptLanguage`. Returns the
`x-is-human` value. (JS ctor: `new BotIDHeaderInput(script, userAgent, ip, acceptLanguage)`.)

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

For mobile, the `x-kpsdk-dv` header is hardcoded (the API can't return it):
```
QkZWEmcDRUBEDloaAg8GABpSDxVEX1JfXBRZRQF5VRoJFFozUQtXBABQGwEPHA==
QkZWEmcDRUBEDloaAg8GABpRDxVEX1JfXBRZRQF5VRoJFFozUQtXBABRGwEPHA==
```

---

## Kasada status-code summary

| Code | Meaning | Action |
|---|---|---|
| `429` | Challenge (homepage in Flow 1, `/fp` in Flow 2, or a protected endpoint when tokens expire) | Run/re-run the payload → `/tl` → POW flow |
| `200` `{"reload":true}` on `/tl` | Challenge accepted | Save `x-kpsdk-ct`/`x-kpsdk-st` + cookies, retry original |

**Final headers on protected requests:** Kasada cookies + `x-kpsdk-ct` + `x-kpsdk-cd`
(fresh POW every request) + `x-kpsdk-h`/`x-kpsdk-v` where the browser sends them.
