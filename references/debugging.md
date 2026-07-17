# Debugging Guide

Start here when an integration is failing. Work top-down: the cross-cutting causes are
far more common than product-specific bugs. **A valid payload from the API that still
gets blocked is almost always a TLS / header / IP / cookie problem in your own client.**

## Triage: first five questions

1. **Does the API return a payload with an empty `error`?** If `error` is non-empty, the
   inputs are wrong (see "API-side errors" below) — fix inputs, not your HTTP client.
2. **Are you using a browser-grade TLS client** (not `requests`/`axios`/`net/http`)?
3. **Is your header order captured from the real wire** (via powhttp — it preserves wire
   order; Charles/DevTools normalize it)?
4. **Is the IP you pass to the API the same IP the target sees** (sticky proxy)?
5. **Is your cookie jar clean** (no missing/duplicate/wrong-domain cookies)?

If 2–5 aren't all "yes", fix those first — see `references/tls-and-headers.md`.

## Cross-cutting symptoms → causes → fixes

| Symptom | Likely cause | Fix |
|---|---|---|
| API payload is valid but target still blocks | TLS fingerprint or header order not matching a real browser | Use a Chrome-profile TLS client (latest available profile + random ext order, HTTP/3 disabled); capture real header order with powhttp and diff it |
| Works locally, fails behind proxy | Rotating proxy → API `ip` ≠ target-facing IP | Switch to **sticky/session** proxies; fetch IP via `/ip` through the same proxy |
| Intermittent blocks, "sometimes works" | Broken cookie jar (duplicate/missing cookies) or IP changing mid-session | One clean jar per session; sticky IP; don't rotate mid-flow |
| Blocked immediately, never passes | `sec-ch-ua` / UA / platform version mismatch, or datacenter IP | Align UA + `sec-ch-ua` + `sec-ch-ua-platform`; try residential/mobile IP |
| `priority` header in wrong position / subtle order bug | `cookie` missing from your header-order list | Add `cookie` to the header-order key even when sending no cookies |
| Requests fail with a length/duplicate error | Manually set `Content-Length` | Never set it — let the client compute it |
| DataDome/others reject despite correct UA | Hardcoded `sec-ch-ua-full-version-list` | Replay the `headers` object the API returns; never hardcode it |
| Large-body request rejected or slow | Uncompressed utmvc/Kasada payload | Compress (zstd/gzip/br) + set `content-encoding`; SDKs auto-compress > 1000 bytes |
| `missing api key` / signature errors | Missing `x-api-key`, or expired/wrong JWT | Set `x-api-key`; check JWT `exp` (short-lived) and the signing key; see `authentication.md` |

## API-side errors (non-empty `error` in the response)

The SDK surfaces these as `api returned with: <error>` (Go), `API returned with error:`
(Python), or `InvalidApiResponseError` (JS). These mean the **inputs** are wrong, not the
HTTP client:
- Missing/empty required field (e.g. `ip`, `script`, a cookie value).
- `script` not the full body (truncated, or you sent the HTML page instead of the script).
- Stale/empty cookie values (`abck`/`bmsz` not re-read from the jar before the call).
- Wrong `scriptUrl`/`pageUrl` (must be the real URLs from the page).
- Parser returned nothing (script path/var not found) → you passed the wrong HTML.

Fix by logging each input right before the call and confirming it matches what a browser
would have at that step.

## Akamai

| Symptom | Cause | Fix |
|---|---|---|
| `_abck` never becomes valid after 3 sensors | TLS/header config wrong (per docs, the SDK caps at 3 — if still failing it's your client) | Fix TLS/header order; confirm `bm_sz` present; verify `~0~` vs 3-post rule |
| Second sensor rejected | Sent `script` again, or omitted `context` | After the first sensor: omit `script`, include the returned `context` |
| Passes then blocks on login/checkout | `_abck` invalidated by the protected action | Regenerate a sensor; use `IsCookieInvalidated` to detect and post 1 more |
| `428` won't clear | Wrong `provider` flow, or submitted before the mandatory wait | Branch on `provider`; **wait the full `chlg_duration`** (crypto/adaptive); success = `sec_cpt` has `~3~` |
| `429 {"t":...}` mid-session | SBSD block | Reuse stored path/UUID/script; POST fresh payload to `/[path]?t=<token>` |
| SBSD passive not working | Only posted index 0 | Post **index 0 then index 1**; use `sbsd_o` or `bm_so` for `o` |
| `version` seems wrong | Set to something other than `"3"` (e.g. a stale `"2"` from an old SDK comment) | Use `"3"` — it's basically always `3` |
| Script path 404 / parser empty | Hardcoded or stale path | Parse the path from **every** page response; never hardcode |

## Incapsula

| Symptom | Cause | Fix |
|---|---|---|
| reese84 challenge persists after posting token | Token invalid or IP blocked | Verify sticky IP; re-solve; check you saved `token` as `reese84` on the returned `cookieDomain` |
| Works then blocks after ~15 min | Token expired | Renew **before** `renewInSec` |
| "Pardon Our Interruption" won't clear | Missing PoW, or didn't send full script body | If the browser POSTs `{"f":"gpc"}`, do the PoW step and pass `Pow`; send the full script from the GET |
| utmvc cookie not accepted | Wrong cookie name or missing submit GET | Cookie is **`___utmvc`** (3 underscores); then GET `/_Incapsula_Resource?SWKMTFSR=1&e=<rand float>` |
| utmvc API rejects input | `sessionIds` wrong | Pass the value of **every** `incap_ses_*` cookie; send the real script JS |
| Captcha block | hCaptcha/Geetest — no Hyper endpoint | Solve the captcha yourself; reuse the `incap_sh_*` cookie |

## DataDome

| Symptom | Cause | Fix |
|---|---|---|
| Slider solve has no effect | Proxy hard-blocked (`t:'bv'` / `isIpBanned`) | Change IP — solving can't help a banned proxy |
| `403` won't clear | Solved the wrong challenge type | `i.js`/`rt:'i'` = interstitial; `c.js`/`rt:'c'` = slider — pick the matching flow |
| Slider payload rejected | Wrong images or not base64 | `.jpg` → `puzzle`, `.frag.png` → `piece`, both base64; parse `captchaChallengePath` (newer) or the preload link (older) |
| Interstitial POST fails | Payload reformatted | The payload is an already-concatenated **form-data string** — POST as-is with correct header order |
| Still blocked despite solving | Low trust score | Post **tags** twice (`type=ch` then `le`), taking the `datadome` cookie from the first POST |
| Tags do nothing | Wrong `ddk`/`type`/order | `ddk` is static per site (from the `/js` POST); first `ch`, then `le`; carry the first cookie forward |

## Kasada

| Symptom | Cause | Fix |
|---|---|---|
| `/tl` doesn't return `{"reload":true}` | Payload not decoded, or wrong headers/content-type | **Base64-decode** the payload; POST as `application/octet-stream` with `x-kpsdk-im/ct/dt`; fix header order |
| Protected requests 429 after solving | Reused POW (`x-kpsdk-cd`) | Generate a **fresh** POW for **every** request |
| POW generation fails/rejected | Missing `fc` on an `/mfc` site (or sending it when there's no `/mfc`) | If `/mfc` exists, read `x-kpsdk-fc` and pass it; otherwise omit `fc` |
| Works then breaks later | Tokens/cookies expired | Re-solve the whole flow; refresh proactively; keep `x-kpsdk-ct` current |
| Flow 2 fails but Flow 1 works | Referer not set to `/fp` | Set referer to the `/fp` URL on ips.js and `/tl` requests |
| BotID (`x-is-human`) rejected | Stale token or IP changed | Re-GET `c.js`, regenerate `x-is-human`; regenerate on 429 or IP change |

## When to escalate to Hyper Solutions

If TLS/header order, IP, cookies, and inputs are all verified correct and it still fails,
capture a **HAR** of the full failing flow **with powhttp** (not Charles — powhttp keeps
the real wire header order; see `references/tls-and-headers.md`), **sanitize**
cookies/tokens/auth, and open a ticket or
share on Discord (`discord.gg/akamai`). Include: product, language/TLS client, the exact
failing request, and the API response `error` (if any).
