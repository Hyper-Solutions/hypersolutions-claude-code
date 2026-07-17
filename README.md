# Hyper Solutions — Claude Code Plugin

A Claude Code [plugin](https://code.claude.com/docs/en/plugins) that teaches Claude to
**integrate and debug** the **Hyper Solutions** anti-bot API (Akamai, Incapsula,
DataDome, Kasada) across the Go, Python, and JavaScript/TypeScript SDKs and the raw REST
API — and to **debug failing requests** by inspecting captured traffic.

It bundles two things:
1. A **skill** (`SKILL.md` + `references/`) with the full integration + debugging
   playbook, including a **request-fingerprinting principles** reference
   (`references/request-rules.md`) for spotting the mistakes that get request-based bots
   blocked (the exhaustive, always-current checks run in the har-analyzer MCP below).
2. Two **MCP servers** (`.mcp.json`):
   - **powhttp** — inspect your script's real wire traffic (header order + TLS
     fingerprint) live and apply those rules to it.
   - **har-analyzer** — a hosted server that runs the same rule set against an exported
     **HAR** and returns structured findings (`analyze_har`).

Ask Claude things like:
- "Help me set up the Akamai sensor flow in Python with tls-client."
- "My DataDome slider solve returns 403 — capture my script with powhttp and tell me what's wrong."
- "Analyze my captured requests and find why I'm getting blocked."
- "Why is my `_abck` cookie never becoming valid?"

## Install

```bash
/plugin marketplace add Hyper-Solutions/hypersolutions-claude-code
/plugin install hypersolutions@hypersolutions
```

The skill auto-activates when your prompt matches Hyper Solutions / anti-bot integration
or request-debugging work (see the `description` in `SKILL.md`).

### Development

To work on the plugin locally, load it from a checkout instead of the marketplace:

```bash
claude --plugin-dir /path/to/hypersolutions-claude-code
# or, in an existing session, reload after editing:
/reload-plugins
```

## Using the powhttp request debugger

The bundled MCP (`.mcp.json`) points at powhttp's local MCP server
(`http://localhost:8383/mcp`). To use it:

1. Install and run [powhttp](https://powhttp.com); click **"Run MCP server"**.
2. Route your failing script's traffic through powhttp's proxy (`http://127.0.0.1:8080`)
   and run the flow.
3. Ask Claude to debug it — it will query the captured requests via the `powhttp` MCP
   tools and analyze header order, TLS fingerprint, cookies, and client hints.

If powhttp isn't running the MCP simply has no tools available; you can still analyze a
HAR the user exports by applying the same rules. See `references/powhttp-mcp.md` and
`references/request-rules.md`.

## Using the HAR analyzer

The bundled `har-analyzer` MCP (`.mcp.json`) is a **hosted** server
(`https://har-mcp.hypersolutions.co/mcp`) that runs the Hyper Solutions fingerprint rule
set against an exported HAR. It's the fastest way to triage a HAR a customer sends you.

1. Set your API key in the environment Claude Code runs in:
   ```bash
   export HYPERSOLUTIONS_API_KEY=<your-key>   # from https://hypersolutions.co/keys
   ```
   The config sends it as the `x-api-key` header; any valid Hyper Solutions key works.
2. Ask Claude to analyze a `.har` file — it calls the `analyze_har` tool and reports the
   findings (severity, category, fix) plus the detected anti-bot product.

A HAR lacks the true wire header order and TLS fingerprint, so a clean result doesn't
rule out those — prefer powhttp for the live wire. See `references/har-analyzer-mcp.md`.

## What's inside

```
.claude-plugin/plugin.json    Plugin manifest
.mcp.json                     Bundled MCP servers: powhttp (local) + har-analyzer (hosted)
SKILL.md                      Entry point: mental model, requirements, routing, debugging
scripts/sec_ch_ua.py          Compute the exact sec-ch-ua (GREASE) for a Chrome version
references/
  authentication.md           x-api-key, JWT x-signature, organization headers
  tls-and-headers.md          TLS fingerprinting, header order, IP/proxy, Chrome version
  akamai.md                   Sensor (_abck), sec-cpt 428, SBSD 429, pixel
  incapsula.md                reese84, reese84 dynamic, utmvc, captcha block
  datadome.md                 interstitial, slider, tags
  kasada.md                   Flow 1/2, payload/cd/botid, POW, Vercel BotID
  api-reference.md            All endpoints, fields, per-SDK signatures, raw HTTP
  powhttp-mcp.md              Live request-capture debugging via the powhttp MCP
  har-analyzer-mcp.md         Automated HAR fingerprint analysis via the har-analyzer MCP
  request-rules.md            Fingerprint principles for powhttp/live captures & writing requests
  debugging.md                Symptom → cause → fix
```

## Maintaining this plugin (IP boundary)

Everything shipped in this repo is **public** — a marketplace reader sees it without an API
key. Keep the valuable, evolving detection logic out of it. The rule when editing:

- **Static files** (`SKILL.md`, `references/`, `scripts/`) hold only **how to use the API**
  and **generally-known** browser-fingerprinting facts (header order, sec-ch-ua GREASE,
  public cookie/endpoint names). This is documentation, not the moat.
- **The har-analyzer MCP** (server-side, API-key-gated) holds the **exhaustive and
  current** detection rules — exact thresholds, per-product flow checks, anything that
  changes as detection evolves. New or updated detection logic goes **there, not here**.
- Don't add: reverse-engineering of an anti-bot's internals (obfuscation/VM/payload
  generation), exact internal thresholds, or named customer/target apps. Describe formats
  generically and point users to Hyper Solutions for specifics.

When in doubt: if it teaches someone to *use* the API, it can live here; if it reveals what
HS *knows or checks*, it belongs in the MCP.

## Links

- Dashboard / API keys: https://hypersolutions.co/keys
- Docs: https://docs.hypersolutions.co
- Examples: https://github.com/Hyper-Solutions/hypersolutions-examples
- SDKs: [Go](https://github.com/Hyper-Solutions/hyper-sdk-go) ·
  [Python](https://github.com/Hyper-Solutions/hyper-sdk-py) ·
  [JS/TS](https://github.com/Hyper-Solutions/hyper-sdk-js)
- Support: Discord `discord.gg/akamai`
