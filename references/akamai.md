# Akamai Bot Manager

Endpoints (host `https://akm.hypersolutions.co`):

| Operation | Endpoint | Go | Python | JS/TS |
|---|---|---|---|---|
| Sensor (`_abck`) | `POST /v2/sensor` | `GenerateSensorData` | `generate_sensor_data` | `generateSensorData` |
| Pixel | `POST /pixel` | `GeneratePixelData` | `generate_pixel_data` | `generatePixelData` |
| SBSD | `POST /sbsd` | `GenerateSbsdData` | `generate_sbsd_data` | `generateSbsdPayload` |
| Telemetry header | `POST /v1/telemetry` | `GenerateTelemetry` | `generate_telemetry` | `generateTelemetry` |
| get_params path | `POST /v1/telemetry/params` | `GetTelemetryParams` | `get_telemetry_params` | `getTelemetryParams` |

Identify Akamai by the `_abck` + `bm_sz` cookies and a dynamic
`<script src="/xxxx/yyyy/...">` near the end of the body. Requires a Chrome UA (Windows recommended; macOS also supported).

---

## 1. Standard sensor flow (`_abck` cookie)

The page embeds a dynamically-generated script path. Posting **sensor data** to that
path validates the `_abck` cookie, which the site then checks on protected actions
(login, add-to-cart, checkout).

**Flow:**
1. **GET the protected page** (browser-grade TLS client + correct header order).
2. **Parse the script path** from the HTML — it's unique/dynamic per response and
   **cannot be hardcoded**. Helpers: Go `akamai.ParseScriptPath`, Python
   `parse_akamai_script_path`, JS `parseAkamaiPath`.
3. **GET the script content**; keep the entire body (same TLS client, correct referer,
   shared cookie jar).
4. **Generate the sensor** via `POST /v2/sensor`.
5. **POST the sensor** to the script path as JSON: `{"sensor_data":"<generated>"}`.
   The response updates `_abck` via `Set-Cookie`.
6. **Validate & repeat.** If `_abck` contains `~0~` you may proceed. If the site does
   **not** use the `~0~` indicator, **post exactly 3 sensors** before proceeding.
   Sensors after the first must **omit `script`** and **include the returned `context`**.
7. **Perform the protected action.** After it, `_abck` is typically invalidated —
   regenerate a sensor before the next protected action.

### `SensorInput` fields

| Field (Go/JS) | Python | Meaning |
|---|---|---|
| `abck` | `abck` | Current `_abck` cookie value — read fresh from the jar every call |
| `bmsz` | `bmsz` | Current `bm_sz` cookie value |
| `version` | `version` | Akamai version — use `"3"` (basically always `3`; the SDK comment's "usually `2`" is stale) |
| `pageUrl` | `page_url` | Page URL that loaded the script (= referer on sensor posts) |
| `userAgent` | `user_agent` | Chrome Windows/macOS UA |
| `script` | `script` | Full script body — **first sensor only**; mutually exclusive with `context` |
| `scriptUrl` | `script_url` | Full URL you POST sensor data to |
| `acceptLanguage` | `accept_language` | e.g. `en-US,en;q=0.9` |
| `ip` | `ip` | Client/proxy IP (required) |
| `context` | `context` | Empty on first request; the returned `context` afterward |

Returns a `SensorResult`: `Payload`/`payload` is the sensor string, `Context`/`context` feeds
the next call, `ClientHints`/`client_hints`/`clientHints` are the device's client hints.

### Cookie-validity helpers

- `IsCookieValid(cookie, requestCount)` / `is_cookie_valid` / `isAkamaiCookieValid` —
  true means the cookie is valid for that request count and you may stop posting sensors.
- `IsCookieInvalidated(cookie)` / `is_cookie_invalidated` / `isAkamaiCookieInvalidated` —
  true means a protected endpoint invalidated the session (cookie tail like `~0~-1~-1`);
  post **one** more sensor to re-validate.

### Best practices / gotchas

- Never hardcode the script path — parse it from every page.
- Fetch the script **once per session**; always save and reuse `context`.
- **Max 3 sensors.** If it still fails after 3, the problem is your **TLS client or
  header configuration**, not the payload.
- Keep the same UA, TLS fingerprint, and IP throughout.

---

## 2. SEC-CPT challenge — HTTP 428

`428 Precondition Required` signals a sec-cpt challenge. Body:
`{"sec-cp-challenge":"true","provider":"crypto",...}`. **The `provider` field selects
the flow.** A solved challenge yields a `sec_cpt` cookie containing `~3~`. Required
cookies: `sec_cpt` (status), `bm_sz` and `_abck` (needed to generate sensors).

SDK challenge helpers:
- Go: `akamai.ParseSecCptChallenge(html)` / `ParseSecCptChallengeFromJson(json)` →
  `*SecCptChallenge`; `.GenerateSecCptPayload(cookie)`, `.Sleep()` / `.SleepWithContext(ctx)`.
- Python: `SecCptChallenge.parse(html)` / `.parse_from_json(json)`;
  `.generate_sec_cpt_payload(cookie)`, `.sleep()`. Also `SecCptChallengeData`.
- JS: `parseChallengeHTML(src)` / `parseChallengeJSON(src)` → `Challenge`;
  `challenge.wait()`, `CryptoChallenge.generatePayload(cookie)`,
  `challenge.updateCryptoChallenge(resp)`, `hasCryptoChallenge()`.

### Provider quick reference

| Aspect | Crypto | Behavioral | Adaptive |
|---|---|---|---|
| Mandatory wait | **Yes** (`chlg_duration`) | No | **Yes** (`chlg_duration`) |
| Proof-of-Work | Yes | No | Yes (`count` answers) |
| Sensor posts | No | Yes (1–3) | Yes (1–3, after PoW) |
| POST endpoint | `/_sec/verify?provider=crypto` | script endpoint from branding page | `/_sec/verify?provider=adaptive` **and** script endpoint |
| Verify endpoint | `/_sec/cp_challenge/verify` (static) | dynamic `verify_url` | `/_sec/cp_challenge/verify` (static) — **not** the dynamic `verify_url` |
| Success | `sec_cpt` contains `~3~` | same | same |

**Crypto** (proof-of-work + mandatory wait): parse challenge (HTML iframe with base64
`challenge` + `data-duration` + `src`, or direct JSON) → **wait the full `chlg_duration`
(server-enforced, submitting early fails)** → generate PoW payload (`token` + computed
`answers` from nonce/timestamp/difficulty) → `POST /_sec/verify?provider=crypto` →
`GET /_sec/cp_challenge/verify` → confirm `sec_cpt` has `~3~`.

**Behavioral** (sensor data): GET the `branding_cust_url` page → parse & GET the Akamai
script → post sensor data with a **fresh context**, include `_abck`, loop up to **3**
posts (break once `sec_cpt` is set) → GET the **dynamic** `verify_url` → confirm `~3~`.

**Adaptive** (PoW then behavioral): parse → **wait `chlg_duration`** → generate PoW with
`answers` count matching the `count` field → `POST /_sec/verify?provider=adaptive`
(e.g. `{"token":"...","answers":["0.66463d05840cd"]}`) → then the behavioral sensor flow
(branding → script → up to 3 sensors, fresh context, include `_abck`) →
`GET /_sec/cp_challenge/verify` (**static**) → success body `{"success":"true"}` →
confirm `sec_cpt` has `~3~`.

Notes: a sec-cpt challenge can appear on initial page load **or** mid-session on an API
call. Keep client hints (`sec-ch-ua`, `sec-ch-ua-mobile`, `sec-ch-ua-platform`)
consistent throughout.

---

## 3. SBSD (State Based Scraping Detection)

`POST /sbsd`. Submit each generated payload to the target as `{"body":"<generated>"}`.
Returns an `SbsdResult` (`payload`, `context`, client hints).

### `SbsdInput` fields

| Field (Go) | Python | JS ctor arg | Meaning |
|---|---|---|---|
| `UserAgent` | `user_agent` | `userAgent` | Chrome Windows/macOS UA |
| `Uuid` | `uuid` | `uuid` | The `v` UUID from the SBSD script URL |
| `PageUrl` | `page_url` | `pageUrl` | Page URL |
| `OCookie` (json `o`) | `o_cookie` | `o_cookie` (field `o`) | The `sbsd_o` **or** `bm_so` cookie value |
| `Script` | `script` | `script` | SBSD script body: **first call only**; mutually exclusive with `context` |
| `AcceptLanguage` | `accept_language` | `acceptLanguage` | Accept-Language |
| `IP` | `ip` | `ip` | Client/proxy IP |
| `Context` | `context` | `context` (optional) | Empty on the first call; the returned `context` afterward |
| `ScriptUrl` | `script_url` | `scriptUrl` (optional) | Absolute src of the SBSD script tag, **query included**, exactly as the page loaded it (`...?v=<uuid>`, plus `&t=...` on a hard block) |

> JS `SbsdInput` constructor order differs from field order:
> `new SbsdInput(uuid, o_cookie, pageUrl, userAgent, script, ip, acceptLanguage, context?, scriptUrl?)`.

**`scriptUrl`** (optional, recommended): the SBSD fingerprint includes signals about the
script itself (its resource-timing entry, and whether it sits on a block page with a `t`
parameter). With `scriptUrl` the payload carries the script's own values; without it the API
uses defaults. When set it must be an http(s) URL with a host and path, else the API answers
`invalid scriptUrl, expected the absolute src of the SBSD script tag`. Fetch the script from
that same URL. SDKs: Go v4.0.0 `ScriptUrl`, Python 4.0.0 `script_url`, JS 5.0.0 `scriptUrl`.

**`script` / `context` rule.** The **first** SBSD call of a session sends `script` and
**no** `context`; its response returns a `context`. **Every call after it sends that
`context` and must not send `script`**: the two fields are mutually exclusive and a request
carrying both is rejected. This keeps you from re-uploading the script (roughly half a
megabyte) on every call.

Passing the context **improves SBSD success rates**. It is optional today and becomes
**mandatory soon**, so wire it up now. The current SDKs (Go v4, Python 4.0.0, JS 5.0.0) have
**no `index`**: an empty context starts a chain (the fingerprint payload), a non-empty one
chains events. A **hard block** (an SBSD POST with a `t` parameter) always starts a new
chain: send `script` and an **empty** context, never one from an earlier call. (The raw API
still reads `index` only when no context is sent.) `hyper-sdk-playwright` handles all of
this automatically.

SBSD appears in **three modes**:

**(a) Passive / basic** — page loads normally but includes an SBSD script with a `v`
UUID and **no `t`**: `<script src="/6mG.../J1CmB4HUQ?v=99b02ce6-...">`. Extract path+UUID
(regex `([a-z\d/\-_\.]+)\?v=([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})`), GET the script, then **post two payloads**,
each to `POST /[path]` body `{"body":"<payload>"}`. The first call sends `script` and no
context (the fingerprint); the second sends the `context` it returned and no `script`. Pass
the script tag's full src as `scriptUrl` on both. Continue normally.

**(b) Hard challenge** — initial GET returns a blocking challenge page whose script has
**both** `v` and `t`: `?v=99b02ce6-...&t=183446612`. Extract with
`([a-z\d/\-_\.]+)\?v=([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})(?:&[^"']*?\bt=([^"'&]+))?[^"']*["']`. GET `/[path]?v=[v]&t=[t]` → generate one
payload (`o` = existing `sbsd_o`, else `bm_so`) → `POST /[path]?t=[t]` body
`{"body":"<payload>"}` → GET `/` returns real content. (Single payload. A hard block always
starts a new chain: send `script`, an empty context, and the full src with `t` as
`scriptUrl`; keep the returned `context` for later calls.)

**(c) 429 block** — a protected call returns **HTTP 429** with body `{"t":"183446612"}`
(token only). React: extract `t`; reuse the **stored** script path, `v` UUID and script
body; generate a fresh payload. This POST carries a `t` parameter, so it is a hard block and
starts a **new chain**: send `script` and an **empty** context, not the context from an
earlier call (pass the script src as `scriptUrl`). `POST /[scriptPath]?t=<token>` body
`{"body":"<payload>"}`; keep the returned `context` for later calls; retry the original
request. You must store path/UUID/script **before** you start making protected requests.

---

## 4. Pixel challenge

`POST /pixel`. **Not required by most sites** — the presence of the pixel script does
**not** mean pixel is enforced. Discuss with support before implementing.

`PixelInput` fields: `userAgent` (Chrome Windows/macOS), `htmlVar`, `scriptVar`,
`acceptLanguage`, `ip`. Returns the pixel payload string.

Parse helpers:
- `ParsePixelHtmlVar` / `parse_pixel_html_var` / `parsePixelHtmlVar` — the
  `bazadebezolkohpepadr="(\d+)"` HTML var.
- `ParsePixelScriptURL` / `parse_pixel_script_url` / `parsePixelScriptUrl` — returns
  `(scriptUrl, postUrl)`; the POST URL prefixes the last path segment with `pixel_`
  (e.g. `.../akam/13/abc` → `.../akam/13/pixel_abc`).
- `ParsePixelScriptVar` / `parse_pixel_script_var` / `parsePixelScriptVar` — the dynamic
  script var.

---

## 5. Akamai-BM-Telemetry header

Some sites protect their **API host** with an `Akamai-BM-Telemetry` request header instead
of a sensor post (first seen on Paylogic). The page loads the normal Akamai script, but the
script attaches a freshly built header to every protected XHR/fetch call.

**Recognise it:** protected API calls carry
`Akamai-BM-Telemetry: a=<_abck id>&&&e=<bm_sz>&&&sensor_data=<base64>&&&j=<j>`; there is
**no** `sensor_data` POST to the script URL; the page makes one
`GET /_bm/get_params?type=web-jsto&v=<tag>` whose JSON has a `j`; the protected host answers
**403** without a valid header. (`a` is only filled when the `_abck` cookie's second field is
`-1`.)

**Flow:**
1. Load the page, parse and GET the Akamai script as in section 1 (keep the script URL).
2. `POST /v1/telemetry/params` with `pageUrl` and `script` (or a `context`) → `payload` = the
   get_params path exactly as the browser requests it (raw tag, `+ / =` **not** encoded:
   request it as returned) and a `context` that replaces the script on the first header. Not
   counted as usage.
3. `GET <page origin><path>` **once per session** with the page's cookies; keep `j`
   **verbatim** (still URL-encoded, e.g. `AAQAAAAG%2f%2f...`).
4. Before **every** protected request: `POST /v1/telemetry` with the sensor fields + `j` and
   the previous `context` (first call: the context from step 2, no script) → send `payload`
   verbatim as `Akamai-BM-Telemetry`, keep the new `context`. **Never reuse a header.**

`/v1/telemetry` input = the `SensorInput` fields (`abck`, `bmsz`, `pageUrl`, `scriptUrl`,
`userAgent`, `acceptLanguage`, `ip`, `script` or `context`) plus optional `j`; no `version`
needed (`"1.75"`/`"2"` are rejected: v3 dynamic scripts only). `scriptUrl` must be the
full Akamai script URL, no query. Output: `payload` (the header value), `context`, client
hints (`headers`).

SDKs (Go v4.0.0 / Python 4.0.0 / JS 5.0.0):
- Go: `session.GetTelemetryParams(ctx, &hyper.TelemetryParamsInput{PageUrl, Script})` →
  `.Path`, `.Context`; `session.GenerateTelemetry(ctx, &hyper.TelemetryInput{SensorInput:
  hyper.SensorInput{...Context}, J: j})` → `.Header`, `.Context`, `.ClientHints`.
- Python: `get_telemetry_params(TelemetryParamsInput(page_url, script))` → `.path`,
  `.context`; `generate_telemetry(TelemetryInput(abck=, bmsz=, page_url=, user_agent=, ip=,
  accept_language=, context=, script="", script_url=, j=))` → `.header`, `.context`.
- JS: `getTelemetryParams(session, new TelemetryParamsInput(pageUrl, script))`;
  `generateTelemetry(session, new TelemetryInput(abck, bmsz, pageUrl, userAgent, ip,
  acceptLanguage, context, script, scriptUrl, j))` → `{header, context, clientHints}`.
- `hyper-sdk-playwright` 1.0.0-beta.16: `AkamaiHandler` replaces the header automatically.

**Gotchas:**
- Use the cookies the **page** holds. When the protected calls go to another host without
  credentials (Paylogic), the browser sends that host no cookies and ignores its
  `Set-Cookie`, so `_abck`/`bm_sz` stay the page-load values; the header's `e` must be that
  `bm_sz`. Send the protected host no cookies either.
- One header per request, context chained. A reused header or context fails after the
  first calls.
- `j` missing or re-encoded: send it exactly as get_params returned it.
- Cross-origin protected calls also need the CORS preflight a browser sends
  (`access-control-request-headers: akamai-bm-telemetry`, plus `authorization` when sent).
- Working examples: `akamai-telemetry/` in hypersolutions-examples (Go, Python, Node).

---

## Akamai status-code summary

| Code | Meaning | Action |
|---|---|---|
| `428` | SEC-CPT challenge (`provider` = crypto / behavioral / adaptive) | Solve per provider; success = `sec_cpt` has `~3~` |
| `429` with `{"t":...}` | SBSD block | Reuse stored path/UUID/script; new chain (script, empty context); POST fresh payload to `/[path]?t=<token>` |
| `403` on a protected API call that carries `Akamai-BM-Telemetry` | Missing, reused or invalid telemetry header | Fresh `/v1/telemetry` header per request, chained `context`, verbatim `j`, page-load `_abck`/`bm_sz`, real script URL (section 5) |
