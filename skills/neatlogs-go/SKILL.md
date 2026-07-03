---
name: neatlogs-go
description: Use when adding neatlogs observability to a Go project — Google Gemini (genai), Google ADK agents, or custom code. Covers Init, WrapGenAI, ADK passthrough, Trace, and Identify (sessions & end-users).
compatibility: Neatlogs Wizard Agent
metadata:
  author: neatlogs
  version: "1.0"
  language: go
  framework: genai
---

# Neatlogs Go Setup — `neatlogs-go`

The Go SDK is **OpenTelemetry-based**. `neatlogs.Init()` registers the global
OTel `TracerProvider`, so any OTel-native framework (notably **Google ADK**) is
captured automatically — and `WrapGenAI()` adds a thin wrapper for the
`google.golang.org/genai` client. Export is OTLP/HTTP to `{endpoint}/v1/traces`.

Module: `github.com/neatlogs/neatlogs-go` (requires Go 1.25+).

```bash
go get github.com/neatlogs/neatlogs-go
```

## The small public API most integrations need

`neatlogs.Init(ctx, Config{...}) (ShutdownFunc, error)`, `neatlogs.Trace(ctx, name)`,
`neatlogs.WrapGenAI(client)`, `neatlogs.Identify(ctx, IdentifyOptions{...})`, and
`contrib/adk.WrapModel(model)` for ADK message I/O.

## Core mechanism

1. **`Init` once, at startup**, and `defer` its shutdown:
   ```go
   shutdown, err := neatlogs.Init(ctx, neatlogs.Config{
       APIKey:       os.Getenv("NEATLOGS_API_KEY"), // falls back to NEATLOGS_API_KEY
       WorkflowName: "my-service",
   })
   if err != nil { log.Fatal(err) }
   defer shutdown(ctx)
   ```
2. **Gemini** — wrap the genai client (one added line); call it exactly as normal:
   ```go
   gc := neatlogs.WrapGenAI(client)                // client = *genai.Client
   resp, err := gc.GenerateContent(ctx, "gemini-2.5-flash", contents, cfg)
   ```
3. **Google ADK** — nothing to wrap for the trace structure: because `Init`
   installed the global provider, ADK's own spans are captured. To also record
   prompt/response TEXT (ADK puts it on logs, not spans), wrap the model:
   ```go
   import nladk "github.com/neatlogs/neatlogs-go/contrib/adk"
   model := nladk.WrapModel(geminiModel)           // I/O capture only — NOT a root
   ```
4. **Custom code** — open a span you control:
   ```go
   ctx, span, end := neatlogs.Trace(ctx, "handle_request")
   defer end()
   ```

## Steps

1. **Install** → `references/1-install.md`
2. **Add Init (+ deferred shutdown)** → `references/2-add-init.md`
3. **Set environment variables** → `references/3-set-env.md`
4. **Wrap Gemini / ADK** → `references/4-wrap-genai-adk.md`
5. **Trace custom code** → `references/5-trace-custom-code.md`
6. **Sessions & end-users (`Identify`)** → `references/sessions-and-end-users.md`

## Rules (apply to ALL steps)

- `neatlogs.Init()` MUST include `APIKey: os.Getenv("NEATLOGS_API_KEY")` (or set the env var) — without it, export is disabled and spans are dropped silently.
- `Init` is single-shot; call it once at startup. Always `defer shutdown(ctx)` (or call it before exit) so buffered spans flush.
- **Do NOT** wrap ADK for trace structure — `Init` already captures ADK's OTel spans. `contrib/adk.WrapModel` only ADDS message I/O onto ADK's existing `generate_content` span; it is NOT an auto-root.
- Session & end-user identity is per-request — set it with `neatlogs.Identify(ctx, ...)`, NEVER on `Init`. It rides on `ctx`. See step 6.
- Pass the `ctx` from `Identify` / `Trace` down into whatever runs the turn — Go propagates identity and parent-span through `context.Context`.
- Never hardcode the API key; use `os.Getenv`.

## `neatlogs.Init()` Config Reference

| Field | Type | Default | Description |
|---|---|---|---|
| `APIKey` | `string` | `NEATLOGS_API_KEY` env | Auth key. Empty (after env fallback) → export disabled, spans dropped |
| `Endpoint` | `string` | `NEATLOGS_ENDPOINT` env, then default | Ingestion base URL (without `/v1/traces`) |
| `WorkflowName` | `string` | executable name | Labels this service/run |
| `Tags` | `[]string` | `nil` | Attached to every span as a resource attribute |
| `Debug` | `bool` | `false` | Verbose diagnostics on stderr |
| `DisableExport` | `bool` | `false` | Drop all spans instead of sending (useful in tests) |

> Note: `Init` has NO session / end-user field. Those are per-request — see `Identify` (step 6). Config carries no operator id either; identity is set at the trace boundary.

## Verify

Run with `Debug: true` and confirm spans export to `{endpoint}/v1/traces`, then
check the Neatlogs dashboard. For ADK, confirm the `generate_content` spans carry
input/output messages (that is what `WrapModel` adds).
