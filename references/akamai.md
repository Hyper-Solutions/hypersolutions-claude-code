# Akamai Bot Manager

Endpoints (host `https://akm.hypersolutions.co`):

| Operation | Endpoint | Go | Python | JS/TS |
|---|---|---|---|---|
| Sensor (`_abck`) | `POST /v2/sensor` | `GenerateSensorData` | `generate_sensor_data` | `generateSensorData` |
| Pixel | `POST /pixel` | `GeneratePixelData` | `generate_pixel_data` | `generatePixelData` |
| SBSD | `POST /sbsd` | `GenerateSbsdData` | `generate_sbsd_data` | `generateSbsdPayload` |

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

Returns `(payload, context)` — `payload` is the sensor string, `context` feeds the next call.

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

### `SbsdInput` fields

| Field (Go) | Python | JS ctor arg | Meaning |
|---|---|---|---|
| `Index` (int) | `index` | `index` | Sensor index; post 0 before 1 |
| `UserAgent` | `user_agent` | `userAgent` | Chrome Windows/macOS UA |
| `Uuid` | `uuid` | `uuid` | The `v` UUID from the SBSD script URL |
| `PageUrl` | `page_url` | `pageUrl` | Page URL |
| `OCookie` (json `o`) | `o_cookie` | `o_cookie` (field `o`) | The `sbsd_o` **or** `bm_so` cookie value |
| `Script` | `script` | `script` | SBSD script body |
| `AcceptLanguage` | `accept_language` | `acceptLanguage` | Accept-Language |
| `IP` | `ip` | `ip` | Client/proxy IP |

> JS `SbsdInput` constructor order differs from field order:
> `new SbsdInput(index, uuid, o_cookie, pageUrl, userAgent, script, ip, acceptLanguage)`.

SBSD appears in **three modes**:

**(a) Passive / basic** — page loads normally but includes an SBSD script with a `v`
UUID and **no `t`**: `<script src="/6mG.../J1CmB4HUQ?v=99b02ce6-...">`. Extract path+UUID
(regex `([a-z\d/\-_\.]+)\?v=([^"'&]+)`), GET the script, then **post two sensors, index 0
then index 1**, each to `POST /[path]` body `{"body":"<payload>"}`. Continue normally.

**(b) Hard challenge** — initial GET returns a blocking challenge page whose script has
**both** `v` and `t`: `?v=99b02ce6-...&t=183446612`. Extract with
`([a-z\d/\-_\.]+)\?v=(.*?)(?:&.*?t=(.*?))?["']`. GET `/[path]?v=[v]&t=[t]` → generate one
payload (`o` = existing `sbsd_o`, else `bm_so`) → `POST /[path]?t=[t]` body
`{"body":"<payload>"}` → GET `/` returns real content. (Single sensor; `index` omitted.)

**(c) 429 block** — a protected call returns **HTTP 429** with body `{"t":"183446612"}`
(token only). React: extract `t`; reuse the **stored** script path, `v` UUID, and script
content from a prior solve; generate a fresh payload; `POST /[scriptPath]?t=<token>` body
`{"body":"<payload>"}`; retry the original request. You must store path/UUID/script
**before** you start making protected requests.

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

## Akamai status-code summary

| Code | Meaning | Action |
|---|---|---|
| `428` | SEC-CPT challenge (`provider` = crypto / behavioral / adaptive) | Solve per provider; success = `sec_cpt` has `~3~` |
| `429` with `{"t":...}` | SBSD block | Reuse stored path/UUID/script; POST fresh payload to `/[path]?t=<token>` |
