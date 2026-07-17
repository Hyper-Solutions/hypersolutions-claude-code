# Analyzing a HAR with the har-analyzer MCP

`har-analyzer` is a **hosted** Hyper Solutions MCP server that runs Hyper Solutions'
current fingerprint rule set against an exported **HAR** file and returns structured
findings. Hand it the raw contents of a `.har` and it tells you which requests carry
detection-worthy fingerprint mistakes, how severe each is, and how to fix it — no manual
rule-walking required.

**This server is kept up to date** — its rules are maintained server-side, so it's more
current than the static `references/request-rules.md` reference. When the two disagree,
trust the MCP.

Use it whenever you have a **HAR** but not a live powhttp capture — most often when a
customer sends a HAR of their failing flow, or when you exported one from powhttp /
Charles / DevTools and want a fast, automated first pass. Its findings are most reliable
on a HAR recorded by a debugger that preserves the **real wire header order** — a powhttp
export does; Charles and DevTools normalize it (see the limitation below).

## How it's wired

This plugin registers the server as **`har-analyzer`** (see `.mcp.json`), so its tool
appears namespaced as **`mcp__plugin_hypersolutions_har-analyzer__analyze_har`**. It's
a remote streamable-HTTP server at `https://har-mcp.hypersolutions.co/mcp`.

**Auth:** the server authenticates with any valid Hyper Solutions API key. The bundled
config sends it via the `x-api-key` header from the **`HYPERSOLUTIONS_API_KEY`**
environment variable — the user must have that set in the environment Claude Code runs
in (get a key at https://hypersolutions.co/keys). If the tool returns `access denied`,
the key is missing or invalid.

> If the `analyze_har` tool isn't available, the server isn't registered or the API key
> env var isn't set. You can still analyze the HAR by hand — apply
> `references/request-rules.md` to the entries yourself.

## The tool

### `analyze_har` — analyze an exported HAR
Params:
- `har` (**required**, string): the **raw contents** of the `.har` file — read the file
  and pass its full text. Not a path, not a nested object; the entire HAR JSON as a
  string. Handles files up to ~50MB.
- `verbose_details` (optional, bool, default `false`): include per-request details
  (method, HTTP version, header order, detected agent) in the output. Turn on when you
  need to see the ordering of a specific request; leave off for a quick issue list.

The analysis always targets a **Chrome** profile and includes informational findings.

### What it returns
A structured result (also mirrored as a JSON text block):
- `har_version`, `creator`, `total_entries`, `analyzed_at`
- `detected_products` — which anti-bot(s) the traffic looks like (routes you to the
  matching product reference).
- `issues[]` — the findings, each with:
  - `severity`: `confirmed` (will likely cause detection) · `warning` (may) · `info`
  - `category`: e.g. `header_order`, `header_case`, `sec_ch_ua`, `duplicate_cookies`,
    `content_length`, `cache_headers`, `pseudo_headers`, `accept_language`,
    `accept_encoding`, `chrome_version`, and per-product (`akamai`, `datadome`,
    `kasada`, `incapsula`).
  - `title`, `description`, `suggestion` — the fix.
  - `affected_entries[]` — the `entry_index` + `url` of each request that has this issue
    (issues are deduplicated across entries).
- `summary` — total/confirmed/warning/info counts and an issues-by-category map.
- `request_details[]` — only when `verbose_details: true`.

## Workflow

1. **Get the HAR into the tool.** Read the `.har` file (or take the text the user
   pasted) and call `analyze_har` with it as `har`. Start without `verbose_details`.
2. **Triage by severity.** Report `confirmed` issues first, then `warning`. Each finding
   already carries a `suggestion` — that's the fix to apply.
3. **Identify the product.** Use `detected_products` to open the right reference
   (`references/akamai.md` / `datadome.md` / `kasada.md` / `incapsula.md`) for
   product-specific flow issues.
4. **Map findings to fixes.** Route each issue through `references/debugging.md` and the
   product file; give the exact header/value to change. `references/request-rules.md`
   describes the underlying rules, but it's a static snapshot — this MCP is the current
   source of truth if they differ.
5. **Re-analyze after changes** if the user exports a fresh HAR.

## Limitation — how much a HAR shows depends on the recorder

What the tool can trust depends on **which debugger recorded the HAR**:

- **Header order / pseudo-header order** — only as good as the recorder. A **powhttp**
  export preserves the real wire order, so order findings are trustworthy. A HAR from
  **Charles or DevTools** normalizes/reorders headers and often drops HTTP/2
  pseudo-headers, so treat its order findings as unreliable — a clean order result there
  doesn't mean the wire order is right.
- **TLS fingerprint** — **never** present in a HAR, whatever recorded it. So a clean
  `analyze_har` result never rules out a non-Chrome TLS ClientHello.

For anything the HAR can't show — TLS, or header order from a non-powhttp HAR — escalate
to **powhttp** (`references/powhttp-mcp.md`), which captures the real wire traffic.
powhttp is the ground truth; `analyze_har` is the fast HAR triage.

## Tips

- HAR entries contain live **cookies and tokens**. Don't echo secrets back to the user;
  redact when quoting a header value.
- If `detected_products` is empty but the user says they're blocked, the HAR may be
  missing the anti-bot request itself (only captures the document) — ask for a HAR that
  includes the failing POST (sensor / `reese84` / `datadome` / Kasada endpoint).
- The tool is stateless — one HAR per call. For a multi-flow session, analyze the
  relevant slice.
