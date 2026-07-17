# Authentication

Every request to `*.hypersolutions.co` must carry your API key. There are three
mechanisms. The SDKs implement all of them — you rarely write this by hand, but you
need to understand it for direct API use and for debugging `missing api key` /
signature errors.

Get your API key at https://hypersolutions.co/keys.

## 1. API Key (simplest)

Add the header on every request:

```
x-api-key: <YOUR_API_KEY>
```

That's it. If the key is missing the SDKs raise/return an error before any HTTP call
(Go: `missing api key`; Python: `ValueError("Missing API key")`; JS: `InvalidApiKeyError`).

## 2. API Key + JWT signing (recommended for client-side apps)

Adds `x-signature` alongside `x-api-key`. The JWT is an **HS256** token signed with your
`jwtKey`. The secret stays in your source and is never transmitted, so a leaked request
can't be replayed. Claims:

- `key` = your API key
- `exp` = expiry. **Docs recommend `now + 15s`** to prevent replay; the SDKs' internal
  signer uses `now + 60s`. Either is fine; keep it short.

Passing the key to the SDK turns this on automatically:

- Go: `hyper.NewSession(apiKey).WithJwtKey("jwt-key")`
- Python: `Session(api_key, jwt_key="jwt-key")`
- JS/TS: `new Session(apiKey, "jwt-key")`

Generate manually (matches the SDK):

```go
// Go
import "github.com/golang-jwt/jwt/v5"
func GenerateSignature(apiKey, jwtKey string) (string, error) {
    claims := jwt.MapClaims{"key": apiKey, "exp": time.Now().Add(15 * time.Second).Unix()}
    return jwt.NewWithClaims(jwt.SigningMethodHS256, claims).SignedString([]byte(jwtKey))
}
```
```python
# Python — requires PyJWT (pip install PyJWT)
import jwt, time
def generate_signature(api_key, jwt_key):
    return jwt.encode({"key": api_key, "exp": int(time.time()) + 15}, jwt_key, algorithm="HS256")
```
```javascript
// JS — requires jsonwebtoken
const jwt = require('jsonwebtoken');
function generateSignature(apiKey, jwtKey) {
  return jwt.sign({ key: apiKey, exp: Math.floor(Date.now()/1000) + 15 }, jwtKey, { algorithm: 'HS256' });
}
```

The JS SDK also exports `generateSignature(apiKey, jwtKey)` directly.

## 3. Organizations (owner acting on behalf of users)

Organization owners authenticate API requests for their users with an **App Key** and
**App Secret** (from the organization dashboard). Send **three** headers:

| Header | Value |
|---|---|
| `x-api-key` | The **user's** API key |
| `x-app-key` | Your organization's App Key |
| `x-app-signature` | HS256 JWT signed with your **App Secret**, claims `key`=appKey, `exp`=now+60s |

Enable in the SDKs:

- Go: `hyper.NewSession(userApiKey).WithOrganization(appKey, appSecret)`
- Python: `Session(user_api_key, app_key="...", app_secret="...")`
- JS/TS: `new Session(userApiKey, undefined, appKey, appSecret)`

`x-app-key` / `x-app-signature` are **only** for organization owners. Individual users
use plain `x-api-key`.

## Headers the SDK sets on every request

For reference when replicating in another language:

```
content-type: application/json
accept-encoding: <zstd|gzip>            # matches configured compression
x-api-key: <api key>
x-signature: <jwt>                       # only if jwtKey configured
x-app-key: <app key>                     # only if organization configured
x-app-signature: <jwt>                   # only if organization configured
content-encoding: <zstd|gzip>            # only when the body is compressed (>1000 bytes)
```

Note header names are lowercase as sent by the SDK. Some docs show `X-Api-Key` /
`X-Signature` casing — HTTP header names are case-insensitive, so either works.
