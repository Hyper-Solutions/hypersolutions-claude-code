# Incapsula / Imperva

Endpoints (host `https://incapsula.hypersolutions.co`):

| Operation | Endpoint | Go | Python | JS/TS |
|---|---|---|---|---|
| reese84 sensor | `POST /reese84` | `GenerateReese84Sensor` | `generate_reese84_sensor` | `generateReese84Sensor` |
| utmvc cookie | `POST /utmvc` | `GenerateUtmvcCookie` | `generate_utmvc_cookie` | `generateUtmvcCookie` |

**Which protection is this site using?**
- **reese84** if there's a cookie named `reese84` or an `x-d-token` header.
- **utmvc** if a script loads like `/_Incapsula_Resource?SWJIYLWA=...`.
- A **"Pardon Our Interruption"** page → reese84 **dynamic** variant.

> Naming note: the reese84 input class is `ReeseInput` in Go and Python, but
> `Reese84Input` in JS/TS.

---

## 1. reese84 (background sensor, no challenge page)

The reese84 script path is **static per site** (look for POST requests whose URL
contains `?d=`).

**Flow:**
1. **GET the script URL** (include its query params); save the full body.
2. **Generate the sensor** via `POST /reese84`.
3. **POST the sensor** to `POST /path/to/reese84/script?d=yourdomain.com` with
   `Content-Type: text/plain; charset=utf-8`, body = the generated sensor.
4. **Parse the response** JSON:
   `{"token":"3:abc123...","renewInSec":896,"cookieDomain":"www.example.com"}`.
   Save `token` as the **`reese84`** cookie on `cookieDomain`.
5. **Renew** before `renewInSec` seconds elapse.

### `ReeseInput` / `Reese84Input` fields

| Field (Go) | Python | JS ctor | Meaning |
|---|---|---|---|
| `UserAgent` | `user_agent` | `userAgent` | Chrome Windows/macOS UA |
| `AcceptLanguage` | `accept_language` | `acceptLanguage` | Accept-Language |
| `IP` | `ip` | `ip` | Client/proxy IP |
| `ScriptUrl` | `script_url` | `scriptUrl` | Full script URL (with query, e.g. `?s=...`) |
| `PageUrl` | `pageUrl` | `pageUrl` | Page URL |
| `Pow` | `pow` (default `""`) | `pow?` | PoW string — empty unless required (see dynamic) |
| `Script` | `script` | `script` | Full script body from step 1 |

> JS `Reese84Input` constructor order:
> `new Reese84Input(userAgent, ip, acceptLanguage, pageUrl, script, scriptUrl, pow?)`.

---

## 2. reese84 Dynamic ("Pardon Our Interruption")

Same `POST /reese84` endpoint, but the page is an interruption page and a **PoW** step
may be required. Uses the `pow` field.

**Flow:**
1. **GET the protected page** → HTML contains "Pardon Our Interruption" and a
   `scriptElement.src = "/onalbaine-.../14167535692918208311?s=xcUvM9nI"`.
2. **Extract paths.** SDK helper does both in one call:
   `ParseDynamicReeseScript(html, url)` (Go) / `parse_dynamic_reese_script(html, url)`
   (Python) / `parseDynamicReeseScript(html, urlStr)` (JS) → `(sensorPath, scriptPath)`.
   `sensorPath` is suffixed with `?d=<hostname>`. (Manual regexes: script path without
   query `src\s*=\s*"(\/[^/]+\/[^?]+)\?.*"`; full script path
   `scriptElement\.src\s*=\s*"(.*?)"`.)
3. **GET the full script URL**; store the body (**required** by the API).
4. **PoW (if required).** Detect by observing a browser POST to the reese84 endpoint with
   body `{"f":"gpc"}`. If required: `POST /[scriptPath]?d=yourdomain.com`
   (`Content-Type: text/plain`) body `{"f":"gpc"}` → server returns a JWT-like PoW string
   `"eyJ0eXAiOiJKV1Qi..."`. Save it for the `Pow` field.
5. **Generate the payload** with `ScriptUrl` (full, with `?s=`), `PageUrl`, `Script`
   (step 3 body), and `Pow` (empty string if not required).
6. **POST the payload** to `POST /[scriptPath]?d=yourdomain.com` with headers
   `Content-Type: text/plain; charset=utf-8`, `Accept: application/json; charset=utf-8`,
   `Origin`, `Referer`; body = generated payload. Response
   `{"token":"3:2wlemniq...","renewInSec":896,"cookieDomain":"www.example.com"}`.
7. **Save** `token` as the `reese84` cookie on `cookieDomain`; retry the protected GET.
   If the challenge persists, the token is invalid or the IP is blocked.

SDK dynamic-parse errors (Go): `ErrReeseScriptNotFound`, `ErrNotInterruptionPage`,
`ErrInvalidURL`.

---

## 3. utmvc (`___utmvc` cookie)

`POST /utmvc`. Note the cookie is **`___utmvc`** (three underscores).

**Flow:**
1. **Parse the script path** from the HTML: regex `src="(/_Incapsula_Resource\?[^"]*)"`.
   Helper: `ParseUtmvcScriptPath` / `parse_utmvc_script_path` / `parseUtmvcScriptPath`.
2. **GET the script** to obtain the JS; pass that JS to the API as `script`.
3. **Generate** via `POST /utmvc`; set the returned value as the **`___utmvc`** cookie.
4. **GET the submit path** `/_Incapsula_Resource?SWKMTFSR=1&e=<random>` where `e` is a
   random 64-bit float (e.g. `0.14896897949050825`). Helper: `GetUtmvcSubmitPath()` /
   `get_utmvc_submit_path()` / `generateUtmvcScriptPath()`. If the utmvc cookie is valid
   the server sets it to value `"a"` with max-age 0.
5. **Make your real requests.**

### `UtmvcInput` fields

| Field (Go) | Python | JS ctor | Meaning |
|---|---|---|---|
| `UserAgent` | `user_agent` | `userAgent` | Chrome Windows/macOS UA |
| `SessionIds` | `session_ids` | `sessionIds` | Value of **each** cookie whose name starts with `incap_ses_` |
| `Script` | `script` | `script` | The utmvc script contents |

Returns `(payload, swhanedl)`. JS helpers: `isSessionCookie(name)` (startsWith
`incap_ses_`) and `getSessionIds(cookies)`.

> **Compress the utmvc request body** — it's large. The API supports gzip, br, deflate
> (and zstd). Set the `content-encoding` header. The SDKs auto-compress bodies > 1000
> bytes.

---

## 4. Incapsula Captcha Block (hCaptcha / Geetest)

**No Hyper Solutions endpoint** — you solve the captcha yourself, then reuse the
resulting cookie.

**Flow:** GET page → captcha block HTML with `<script src="/_Incapsula_Resource?SWJIYLWA=...">`
and an `<iframe id="main-iframe" src="/_Incapsula_Resource?SWUDNSAI=31&xinfo=...&incident_id=...&cts=...&mth=GET">`.
Extract the iframe `src` → GET that resource URL → parse the POST URL from
`xhr.open("POST", "/_Incapsula_Resource?SWCGHOEL=v2&dai=...&cts=...")` → solve the
hCaptcha/Geetest → `POST` that URL with body `g-recaptcha-response=<token>` → server
responds `Set-Cookie: incap_sh_*=...` → retry the original GET with the `incap_sh_*` cookie.

---

## Best practices

- Consistent UA, Accept-Language, and header order; TLS fingerprint must match the UA's
  Chrome version.
- Renew reese84 tokens **before** `renewInSec`.
- The public IP must be obtained through the **same proxy path** used for all requests.
