# API Reference — endpoints, fields, SDKs, raw HTTP

Complete surface for direct API use and cross-SDK reference. All endpoints are **POST**,
body `application/json`, unless noted. Auth: see `references/authentication.md`.

## Endpoint map

| Product | Host | Endpoints |
|---|---|---|
| Akamai | `https://akm.hypersolutions.co` | `/v2/sensor`, `/pixel`, `/sbsd`, `/v1/telemetry`, `/v1/telemetry/params` |
| Incapsula | `https://incapsula.hypersolutions.co` | `/reese84`, `/utmvc` |
| DataDome | `https://datadome.hypersolutions.co` | `/slider`, `/interstitial`, `/tags` |
| Kasada | `https://kasada.hypersolutions.co` | `/payload`, `/cd`, `/botid` |
| IP utility | `https://ip.hypersolutions.co` | `GET /ip` |
| Usage/quota | `https://api.hypersolutions.co` | `GET /usage` (personal-org API) |

## Response envelope

Generate endpoints return JSON with a common shape (fields present vary by endpoint):

| Field | Meaning |
|---|---|
| `payload` | The generated string (sensor / cookie / token / telemetry header / get_params path). Kasada `/payload` = base64 (decode it) |
| `context` | Akamai sensor / SBSD context to feed the next call |
| `error` | Non-empty on failure. SDKs surface as `api returned with: <error>` |
| `swhanedl` | Situational (Incapsula utmvc) |
| `headers` | The device's Accept-CH client hints (Akamai sensor/SBSD/telemetry, DataDome, Incapsula reese84). **Kasada `/payload` is different:** `headers` = the `x-kpsdk-*` values every `/tl` request sends, and the hints are in `clientHints` |
| `clientHints` | Kasada `/payload` only: the client hints |

On failure the response carries a non-empty `error`; HTTP non-200 is also an error.

### Client hints

24 keys, lowercase, values ready to send verbatim (do not re-quote): `sec-ch-ua`,
`sec-ch-ua-mobile`, `sec-ch-ua-platform`, `sec-ch-ua-arch`, `sec-ch-ua-bitness`,
`sec-ch-ua-model`, `sec-ch-ua-platform-version`, `sec-ch-ua-full-version`,
`sec-ch-ua-full-version-list`, `sec-ch-ua-wow64`, `sec-ch-ua-form-factors`,
`sec-ch-device-memory`, `sec-ch-dpr`, `sec-ch-viewport-width`, `sec-ch-viewport-height`,
`device-memory`, `dpr`, `viewport-width`, `ect`, `rtt`, `downlink`,
`sec-ch-prefers-color-scheme`, `sec-ch-prefers-reduced-motion`,
`sec-ch-prefers-reduced-transparency`. Absent for Safari UAs on Incapsula and mobile UAs on
Kasada. Not returned by `/pixel`, `/utmvc`, `/v1/telemetry/params`.

Send them like Chrome: `sec-ch-ua`, `sec-ch-ua-mobile`, `sec-ch-ua-platform` on every
secure request; any other hint **only** if the site asked for it in its `Accept-CH` (or
`Critical-CH`) response header, on later requests to that origin. Cross-origin requests (a
separate API host, captcha-delivery, a tags endpoint) get only the three. Use the latest
result's values; never hardcode them, and never send every hint on every request.

### Script hashes (`scriptHash`)

The endpoints that take a challenge script (DataDome `/interstitial` and `/slider`,
Incapsula `/reese84`, Akamai `/v2/sensor`, `/v1/telemetry`, `/v1/telemetry/params` and
`/sbsd`) also accept `scriptHash`: the lowercase hex sha256 of the script exactly as served,
in place of the 600 to 800 KB script.

- **SDKs do it for you.** Keep passing `script`. The SDK sends only the hash and sends the
  script once more when the API answers that it has not seen it. No code changes.
- **`422 {"error":"script_required"}` is expected**, not a bug: it means no client has sent
  that script yet (a new script version, or one unused for 7 days). The SDK retries with the
  script automatically, and every later request for that script needs only the hash. It is
  not billed. Requests the API solves in a real browser also answer it to a hash-only request.
- **Raw HTTP:** send `"scriptHash": sha256hex(script)` without `script`; on a 422
  `script_required`, repeat the same request with `script` and without `scriptHash`. Never
  send both (400). On Akamai, `scriptHash` and `context` are also mutually exclusive: chain
  with `context` exactly as before.
- Incapsula reese84 requires one of `script` or `scriptHash`. DataDome accepts neither, but then
  builds the payload for a fixed bundle version, so always send one.

## Method names by SDK

| Operation | Go (`session.…`) | Python (`session.…`) | JS/TS (`fn(session, …)`) | Result fields |
|---|---|---|---|---|
| Akamai sensor | `GenerateSensorData` | `generate_sensor_data` | `generateSensorData` | payload, context, client hints |
| Akamai pixel | `GeneratePixelData` | `generate_pixel_data` | `generatePixelData` | payload |
| Akamai SBSD | `GenerateSbsdData` | `generate_sbsd_data` | `generateSbsdPayload` | payload, context, client hints |
| Akamai telemetry | `GenerateTelemetry` | `generate_telemetry` | `generateTelemetry` | header, context, client hints |
| Akamai get_params path | `GetTelemetryParams` | `get_telemetry_params` | `getTelemetryParams` | path, context |
| Incapsula reese84 | `GenerateReese84Sensor` | `generate_reese84_sensor` | `generateReese84Sensor` | payload, client hints |
| Incapsula utmvc | `GenerateUtmvcCookie` | `generate_utmvc_cookie` | `generateUtmvcCookie` | payload, swhanedl |
| Kasada payload | `GenerateKasadaPayload` | `generate_kasada_payload` | `generateKasadaPayload` | payload, headers (x-kpsdk-*), client hints |
| Kasada POW | `GenerateKasadaPow` | `generate_kasada_pow` | `generateKasadaPow` | payload (`x-kpsdk-cd`) |
| Kasada BotID | `GenerateBotIDHeader` | `generate_botid_header` | `generateBotIDHeader` | payload (`x-is-human`) |
| DataDome interstitial | `GenerateDataDomeInterstitial` | `generate_interstitial_payload` | `generateInterstitialPayload` | payload, client hints |
| DataDome slider | `GenerateDataDomeSlider` | `generate_slider_payload` | `generateSliderPayload` | payload, client hints |
| DataDome tags | `GenerateDataDomeTags` | `generate_tags_payload` | `generateTagsPayload` | payload, client hints |

Every method returns a result object (Go v4 `*XResult`, Python 4.0.0 dataclass, JS 5.0.0
object): Go `res.Payload` / `res.ClientHints`, Python `res.payload` / `res.client_hints`, JS
`res.payload` / `res.clientHints`. Older SDK majors returned tuples or strings.

Input field names per product are in each product reference file. Per-language input
field styles: **Go** = struct with `json` tags; **Python** = keyword args (snake_case);
**JS/TS** = classes with **positional** constructor args.

### JS constructor arg-order warnings (differ from field order)

```typescript
new SbsdInput(uuid, o_cookie, pageUrl, userAgent, script, ip, acceptLanguage, context?, scriptUrl?)
new TelemetryInput(abck, bmsz, pageUrl, userAgent, ip, acceptLanguage, context, script, scriptUrl, j?)
new TelemetryParamsInput(pageUrl, script?, context?)
new KasadaPayloadInput(userAgent, ipsLink, script, ip, acceptLanguage, strict?)
new Reese84Input(userAgent, ip, acceptLanguage, pageUrl, script, scriptUrl, pow?)
new InterstitialInput(userAgent, deviceLink, html, ip, acceptLanguage, script?)
new SliderInput(userAgent, deviceLink, html, puzzle, piece, parentUrl, ip, acceptLanguage, script?)
new TagsInput(userAgent, ddk, referer, type, ip, acceptLanguage, version, cid?)
new KasadaPowInput(st, ct, domain, fc?, workTime?)
new BotIDHeaderInput(script, userAgent, ip, acceptLanguage)
```

## Session construction & config

| | Go | Python | JS/TS |
|---|---|---|---|
| Construct | `hyper.NewSession(key)` | `Session(key)` / `SessionAsync(key)` | `new Session(key)` |
| JWT | `.WithJwtKey(k)` | `jwt_key=` | 2nd ctor arg |
| Org | `.WithOrganization(k, s)` | `app_key=`, `app_secret=` | 3rd/4th ctor args |
| Custom client | `.WithClient(c)` | `client=` | — (options: `proxy`, `timeout`, `rejectUnauthorized`) |
| Compression | `.WithCompression(hyper.CompressionZstd\|Gzip)` | `compression=True` (gzip) | `options.compression` (gzip) |
| Default timeout | 30s | 30s | 30000ms |
| Default compression | **zstd** | **gzip** | **gzip** |
| Async | — | `SessionAsync` (methods awaitable, HTTP/2) | all ops are `async`/Promise |

## Compression

**Use compression in both directions on basically every call** — request payload **and**
response. The bodies this API handles are large (Akamai sensor/script, Incapsula utmvc,
Kasada), so compressing cuts bandwidth and latency meaningfully.

- **Request payload:** set `Content-Encoding: <enc>` and compress the body.
- **Response:** send `Accept-Encoding` listing the codec(s) you can decode; the API
  compresses its response to match.

**Which codec — pick by your language's support:**
- **zstd** where the language has good native support — e.g. **Go**
  (`.WithCompression(hyper.CompressionZstd)`). Best ratio.
- **gzip** for languages without solid builtin zstd support — **Python** and **JS/TS**
  (their SDK compression is gzip). Universally available.

Supported request encodings: **gzip, deflate, brotli (br), zstd**. The SDK defaults
already follow this rule (Go → zstd, Python/JS → gzip); just enable compression on the
session so it's on for every call. Note the SDKs only auto-compress a request body **once
it exceeds 1000 bytes** — smaller bodies go uncompressed, which is fine.

## Raw HTTP contract (no SDK)

```http
POST /v2/sensor HTTP/2
Host: akm.hypersolutions.co
Content-Type: application/json
Accept-Encoding: zstd, br, gzip
x-api-key: <YOUR_API_KEY>
Content-Encoding: zstd            # only if you compressed the body

{ "abck": "...", "bmsz": "...", "version": "3", "pageUrl": "...", "userAgent": "...",
  "scriptUrl": "...", "acceptLanguage": "en-US,en;q=0.9", "ip": "...",
  "context": "", "script": "<full script on first call only>" }
```

On the first call, `"scriptHash": "<sha256 hex of the script>"` can replace `"script"`; see
**Script hashes** above for the 422 `script_required` retry.

Response:
```json
{ "payload": "<sensor_data>", "context": "<context>", "headers": { "sec-ch-ua-platform": "\"Windows\"", ... }, "error": "" }
```

The JSON field names above are the exact wire names (Go `json` tags). Use them verbatim
in any language. For every product's field list, see its reference file.

## Working examples

The `hypersolutions-examples` repo
(https://github.com/Hyper-Solutions/hypersolutions-examples) has an end-to-end example
for every product × language, pairing the SDK with a real TLS client:

| | Akamai | DataDome | Incapsula | Kasada |
|---|---|---|---|---|
| Go (azuretls) | ✓ | ✓ | ✓ | ✓ |
| Go (bogdanfinn tls-client) | ✓ | ✓ | ✓ | ✓ |
| Node (tlsclientwrapper) | ✓ | ✓ | ✓ | ✓ |
| Python (tls-client, sync) | ✓ | ✓ | ✓ | ✓ |
| Python (rnet/wreq, async) | ✓ (wreq) | ✓ | ✓ | ✓ |

Plus `akamai-telemetry/` (Go bogdanfinn, Python tls-client, Node tlsclientwrapper): the
Akamai-BM-Telemetry flow on a read-only endpoint.

Notes: the Go azuretls vs bogdanfinn variants differ **only** in HTTP plumbing — SDK
calls, header maps, and detection logic are identical. Same for Python tls-client (sync)
vs rnet (async). The **Python Akamai async example actually uses `wreq`** (an
rnet-compatible fork), not `rnet` — its `requirements.txt` omits `rnet`. A high-level
browser-automation path (`hyper-sdk-playwright`'s `AkamaiHandler`) is shown only in
`node/united` and only for Akamai. `node/bb` is a standalone Browserbase demo and does
**not** use the Hyper SDK.

### Minimal end-to-end skeleton (Go, Akamai + bogdanfinn tls-client)

```go
// 1. Build a browser-grade TLS client
jar, _ := cookiejar.New(nil)
client, _ := tlsclient.NewHttpClient(tlsclient.NewNoopLogger(),
    tlsclient.WithClientProfile(profiles.Chrome_133),
    tlsclient.WithNotFollowRedirects(),
    tlsclient.WithRandomTLSExtensionOrder(),
    tlsclient.WithCookieJar(jar),
    tlsclient.WithDisableHttp3(),
)
api := hyper.NewSession(os.Getenv("HYPER_API_KEY"))

// 2. GET page, parse script path, GET script (set http.HeaderOrderKey on every request)
// 3. Loop up to 3 sensors:
for i := 0; i < 3; i++ {
    res, _ := api.GenerateSensorData(context.Background(), &hyper.SensorInput{
        Abck: abck, Bmsz: bmsz, Version: "3", PageUrl: pageURL, UserAgent: ua,
        ScriptUrl: scriptURL, AcceptLanguage: al, IP: ip, Context: sensorContext,
        Script: scriptOnFirstIterationOnly,
    })
    sensorContext = res.Context
    // POST {"sensor_data": res.Payload} to scriptURL; refresh abck/bmsz from jar;
    // send res.ClientHints per the client hints rules
    if akamai.IsCookieValid(abck, i) { break }
}
```

The other languages follow the identical step structure — only the TLS-client plumbing
and the SDK call style (method vs free-function, keyword vs positional args) change.
