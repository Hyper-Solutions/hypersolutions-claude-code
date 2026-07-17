# DataDome

Endpoints (host `https://datadome.hypersolutions.co`):

| Operation | Endpoint | Go | Python | JS/TS |
|---|---|---|---|---|
| Interstitial | `POST /interstitial` | `GenerateDataDomeInterstitial` | `generate_interstitial_payload` | `generateInterstitialPayload` |
| Slider (captcha) | `POST /slider` | `GenerateDataDomeSlider` | `generate_slider_payload` | `generateSliderPayload` |
| Tags | `POST /tags` | `GenerateDataDomeTags` | `generate_tags_payload` | `generateTagsPayload` |

**Identify the challenge.** A block is served as **HTTP 403** with a body containing an
inline `var dd={...}` object. The `dd.rt` field and the referenced JS file distinguish
types:
- `rt:'i'` + `https://ct.captcha-delivery.com/i.js` → **interstitial**
- `rt:'c'` + `https://ct.captcha-delivery.com/c.js` → **slider**
- **tags** are never in a block page — they're proactive telemetry to raise trust.

> **Hard-block gotcha (slider):** if the response has `t` set to `bv`, your **proxy is
> hard-blocked** — solving the challenge will have no effect. The SDKs surface this:
> Go/Python raise `"proxy blocked"`; JS returns `result.isIpBanned === true` (and
> `result.url` is null).

Requires a Chrome UA on all calls (Windows recommended; macOS also supported). From the `dd` object always also keep: the
**blocked URL** (used as `referer`) and the **`datadome` cookie** set on the 403.

---

## 1. Interstitial

Extract from the `dd` object: `cid`, `hsh`, `s`, `b`.

**Flow:**
1. **Build the deviceLink** (SDK helper does this):
   `ParseInterstitialDeviceCheckLink(body, datadomeCookie, referer)` (Go) /
   `parse_interstitial_device_check_link(...)` (Py) /
   `parseInterstitialDeviceCheckUrl(body, cookie, referer)` (JS, returns `null` on
   failure). Result:
   `https://geo.captcha-delivery.com/interstitial/?initialCid={cid}&hash={hsh}&cid={datadomeCookie}&referer={referer}&s={s}&b={b}&dm=cd`
2. **GET the deviceLink**; save the HTML body.
3. **Generate the payload** via `POST /interstitial`.
4. **POST the payload** to `https://geo.captcha-delivery.com/interstitial/` — the payload
   is an **already-concatenated form-data string** (match browser header order).
5. **Parse the response** and update the cookie jar; retry:
   ```json
   {"cookie":"datadome=...; Max-Age=31536000; Domain=.example.com; Path=/; Secure; SameSite=Lax",
    "view":"redirect","url":"https://www.example.com/path"}
   ```

### `DataDomeInterstitialInput` fields

`userAgent` (Chrome Windows/macOS), `deviceLink` (from step 1), `html` (deviceLink GET body),
`acceptLanguage`, `ip`. Returns `{payload, headers}` — replay the returned `headers` on
subsequent requests. (JS ctor: `new InterstitialInput(userAgent, deviceLink, html, ip, acceptLanguage)`.)

---

## 2. Slider (captcha)

Extract from the `dd` object: `cid`, `hsh`, `t`, `s`, `e`.

**Flow:**
1. **Build the deviceLink** (SDK helper — and check for the `bv` hard block here):
   `ParseSliderDeviceCheckLink(body, datadomeCookie, referer)` /
   `parse_slider_device_check_link(...)` / `parseSliderDeviceCheckUrl(...)`. Result:
   `https://geo.captcha-delivery.com/captcha/?initialCid={cid}&hash={hsh}&cid={datadomeCookie}&t={t}&referer={referer}&s={s}&e={e}&dm=cd`
2. **GET the deviceLink**; save the HTML. Extract the puzzle image URL from it:
   - Newer: JS var `captchaChallengePath: 'https://dd.prod.captcha-delivery.com/image/.../hash.jpg'`
     (regex `captchaChallengePath:\s*['"]([^'"]+\.jpg)['"]`); derive the piece by
     replacing `.jpg` → `.frag.png`.
   - Older: `<link rel="preload" href="https://dd.prod.captcha-delivery.com/image/.../hash.jpg">`
     (piece = same URL with `.frag.png`).
3. **GET both images** (no TLS client/cookies needed) and **base64-encode**: the `.jpg`
   → `puzzle`, the `.frag.png` → `piece`.
4. **Generate the payload** via `POST /slider`.
5. **GET the returned check URL** (`https://geo.captcha-delivery.com/captcha/check?cid=...`;
   include the returned `headers`). Response: `{"cookie":"datadome=...; ...; SameSite=Lax"}`.
   Update the cookie jar; retry. (`403` on the check = rejected.)

### `DataDomeSliderInput` fields

`userAgent`, `deviceLink`, `html`, `puzzle` (base64 jpg), `piece` (base64 frag.png),
`parentUrl`, `acceptLanguage`, `ip`. Returns `{payload, headers}`.

---

## 3. Tags

`POST /tags`. Proactive telemetry POSTed to the target's own `/js` endpoint to raise the
session trust score (fewer blocks). Never appears in a block page.

**Flow:** call the API, then POST the returned payload to the target's `/js` endpoint.
Response: `{"status":200,"cookie":"datadome=...; ...; SameSite=Lax"}`. **Post tags twice**,
always taking the `datadome` cookie from the **first** tags POST: first with `type=ch`,
then with `type=le`. Update the `datadome` cookie manually.

### `DataDomeTagsInput` fields

| Field (Go) | Python | Meaning |
|---|---|---|
| `UserAgent` | `user_agent` | Chrome Windows/macOS UA |
| `Cid` | `cid` (default `""`) | Current `datadome` cookie |
| `Ddk` | `ddk` | Sitekey — **static per site**; parse from the browser's `/js` POST |
| `Referer` | `referer` | Referer header on the POST |
| `Type` | `tags_type` (json `type`) | **First call `ch`, second call `le`** |
| `Version` | `version` | Tags version (e.g. `5.1.13`) |
| `AcceptLanguage` | `accept_language` | First language of Accept-Language (default `en-US`) |
| `IP` | `ip` | IP used to post to the target |

> JS ctor order: `new TagsInput(userAgent, ddk, referer, type, ip, acceptLanguage, version, cid?)`.

Returns the tags payload string.

---

## DataDome status-code summary

| Code | Meaning | Action |
|---|---|---|
| `403` + `var dd={...}` | Challenge | Disambiguate via `i.js`/`rt:'i'` (interstitial) vs `c.js`/`rt:'c'` (slider) |
| `t:'bv'` on slider | Proxy hard-blocked | Change IP — solving won't help |
