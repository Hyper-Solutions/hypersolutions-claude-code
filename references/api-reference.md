# API Reference — endpoints, fields, SDKs, raw HTTP

Complete surface for direct API use and cross-SDK reference. All endpoints are **POST**,
body `application/json`, unless noted. Auth: see `references/authentication.md`.

## Endpoint map

| Product | Host | Endpoints |
|---|---|---|
| Akamai | `https://akm.hypersolutions.co` | `/v2/sensor`, `/pixel`, `/sbsd` |
| Incapsula | `https://incapsula.hypersolutions.co` | `/reese84`, `/utmvc` |
| DataDome | `https://datadome.hypersolutions.co` | `/slider`, `/interstitial`, `/tags` |
| Kasada | `https://kasada.hypersolutions.co` | `/payload`, `/cd`, `/botid` |
| IP utility | `https://ip.hypersolutions.co` | `GET /ip` |
| Usage/quota | `https://api.hypersolutions.co` | `GET /usage` (personal-org API) |

## Response envelope

Generate endpoints return JSON with a common shape (fields present vary by endpoint):

| Field | Meaning |
|---|---|
| `payload` | The generated string (sensor / cookie / token). Kasada `/payload` = base64 (decode it) |
| `context` | Akamai sensor context to feed the next call |
| `error` | Non-empty on failure. SDKs surface as `api returned with: <error>` |
| `swhanedl` | Situational (Incapsula utmvc) |
| `headers` | Client-hint headers to **replay on the target**: `sec-ch-device-memory`, `sec-ch-ua-mobile`, `sec-ch-ua-arch`, `sec-ch-ua-platform`, `sec-ch-ua-model`, `sec-ch-ua-full-version-list` |

On failure the response carries a non-empty `error`; HTTP non-200 is also an error. Never
hardcode the values in `headers` — always replay what the API returns.

## Method names by SDK

| Operation | Go (`session.…`) | Python (`session.…`) | JS/TS (`fn(session, …)`) | Returns |
|---|---|---|---|---|
| Akamai sensor | `GenerateSensorData` | `generate_sensor_data` | `generateSensorData` | `{payload, context}` |
| Akamai pixel | `GeneratePixelData` | `generate_pixel_data` | `generatePixelData` | `payload` |
| Akamai SBSD | `GenerateSbsdData` | `generate_sbsd_data` | `generateSbsdPayload` | `payload` |
| Incapsula reese84 | `GenerateReese84Sensor` | `generate_reese84_sensor` | `generateReese84Sensor` | `payload` |
| Incapsula utmvc | `GenerateUtmvcCookie` | `generate_utmvc_cookie` | `generateUtmvcCookie` | `{payload, swhanedl}` |
| Kasada payload | `GenerateKasadaPayload` | `generate_kasada_payload` | `generateKasadaPayload` | `{payload, headers}` |
| Kasada POW | `GenerateKasadaPow` | `generate_kasada_pow` | `generateKasadaPow` | `x-kpsdk-cd` |
| Kasada BotID | `GenerateBotIDHeader` | `generate_botid_header` | `generateBotIDHeader` | `x-is-human` |
| DataDome interstitial | `GenerateDataDomeInterstitial` | `generate_interstitial_payload` | `generateInterstitialPayload` | `{payload, headers}` |
| DataDome slider | `GenerateDataDomeSlider` | `generate_slider_payload` | `generateSliderPayload` | `{payload, headers}` |
| DataDome tags | `GenerateDataDomeTags` | `generate_tags_payload` | `generateTagsPayload` | `payload` |

Input field names per product are in each product reference file. Per-language input
field styles: **Go** = struct with `json` tags; **Python** = keyword args (snake_case);
**JS/TS** = classes with **positional** constructor args.

### JS constructor arg-order warnings (differ from field order)

```typescript
new SbsdInput(index, uuid, o_cookie, pageUrl, userAgent, script, ip, acceptLanguage)
new Reese84Input(userAgent, ip, acceptLanguage, pageUrl, script, scriptUrl, pow?)
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
    sensor, ctx, _ := api.GenerateSensorData(context.Background(), &hyper.SensorInput{
        Abck: abck, Bmsz: bmsz, Version: "3", PageUrl: pageURL, UserAgent: ua,
        ScriptUrl: scriptURL, AcceptLanguage: al, IP: ip, Context: sensorContext,
        Script: scriptOnFirstIterationOnly,
    })
    sensorContext = ctx
    // POST {"sensor_data": sensor} to scriptURL; refresh abck/bmsz from jar
    if akamai.IsCookieValid(abck, i) { break }
}
```

The other languages follow the identical step structure — only the TLS-client plumbing
and the SDK call style (method vs free-function, keyword vs positional args) change.
