---
name: neatlogs-go
description: Use when adding neatlogs observability to a Go project — Google Gemini (genai), direct LLM/provider calls, retrieval, service boundaries, or custom code. Covers Init, WrapGenAI, explicit span helpers (StartLLMSpan / StartRetrieverSpan / StartToolSpanFromHeaders), Trace, and Identify (sessions & end-users).
compatibility: Neatlogs Wizard Agent
metadata:
  author: neatlogs
  version: "1.1"
  language: go
  framework: genai
---

# Neatlogs Go Setup — `neatlogs-go`

The Go SDK is OpenTelemetry-based but keeps to a **private tracer provider**:
`neatlogs.Init()` configures it and **never touches process-global OTel state**
(no `otel.SetTracerProvider` / `SetTextMapPropagator`). So Neatlogs can neither
export nor parent (nor be parented by) a co-tenant tracer like Datadog — and,
symmetrically, OTel-native frameworks are **not** auto-captured. You instrument
explicitly: `WrapGenAI()` wraps a `google.golang.org/genai` client, and a small
set of span helpers cover direct provider calls, retrieval, and boundaries.
Export is OTLP/HTTP to `{endpoint}/v1/traces`.

Module: `github.com/neatlogs/neatlogs-go` (requires Go 1.25+). The Gemini wrapper
lives in a separate module (`contrib/genai`) so its heavy dependency stays out of
apps that only need the core helpers.

```bash
go get github.com/neatlogs/neatlogs-go
go get github.com/neatlogs/neatlogs-go/contrib/genai   # only if wrapping Gemini
```

<Callout type="info">
  `contrib/adk` (Google ADK passthrough + `WrapModel` + A2A helpers) is
  **deprecated and non-functional** under the private-provider design — ADK binds
  to the global provider Neatlogs no longer owns. Instrument model calls and
  boundaries explicitly instead.
</Callout>

## The small public API most integrations need

`neatlogs.Init(ctx, Config{...}) (ShutdownFunc, error)`, `neatlogs.Trace(ctx, name)`,
`neatlogs.StartSpan(ctx, name, kind, attrs...)`, `neatlogs.Identify(ctx, IdentifyOptions{...})`,
`genai.WrapGenAI(client)` (from `contrib/genai`), and the explicit span helpers
`neatlogs.StartLLMSpan`, `neatlogs.StartRetrieverSpan`, `neatlogs.StartToolSpanFromHeaders`,
plus `neatlogs.InjectTraceContext` / `ExtractTraceContext` for cross-process boundaries.

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
   import nlgenai "github.com/neatlogs/neatlogs-go/contrib/genai"
   gc := nlgenai.WrapGenAI(client)                 // client = *genai.Client
   resp, err := gc.GenerateContent(ctx, "gemini-2.5-flash", contents, cfg)
   ```
3. **Direct provider calls (OpenAI/Anthropic/…)** — open an LLM span you fill in:
   ```go
   ctx, llm := neatlogs.StartLLMSpan(ctx, neatlogs.LLMCallOptions{
       Provider: "openai", Model: "gpt-5.5",
       Messages: []neatlogs.LLMMessage{{Role: "user", Content: prompt}},
   })
   defer llm.End()
   // ... real call ...
   llm.SetOutputMessage("assistant", out)
   llm.SetUsage(promptTok, completionTok, totalTok)
   ```
4. **Custom code / boundaries** — open a span you control:
   ```go
   ctx, span, end := neatlogs.Trace(ctx, "handle_request") // workflow root
   defer end()
   ```

## Steps

1. **Install** → `references/1-install.md`
2. **Add Init (+ deferred shutdown)** → `references/2-add-init.md`
3. **Set environment variables** → `references/3-set-env.md`
4. **Wrap Gemini + explicit span helpers** → `references/4-wrap-genai-adk.md`
5. **Trace custom code** → `references/5-trace-custom-code.md`
6. **Sessions & end-users (`Identify`)** → `references/sessions-and-end-users.md`

## Rules (apply to ALL steps)

- `neatlogs.Init()` MUST include `APIKey: os.Getenv("NEATLOGS_API_KEY")` (or set the env var) — without it, export is disabled and spans are dropped silently.
- `Init` is single-shot; call it once at startup. Always `defer shutdown(ctx)` (or call it before exit) so buffered spans flush.
- **The provider is private.** `Init` does NOT register the global OTel provider, so OTel-native frameworks (including Google ADK) are **not** auto-captured. Instrument model calls / boundaries explicitly with `WrapGenAI` or the span helpers. Do NOT reach for `contrib/adk` — it is deprecated and non-functional.
- Gemini wrapping lives in `contrib/genai`: import `nlgenai "github.com/neatlogs/neatlogs-go/contrib/genai"` and call `nlgenai.WrapGenAI(client)` (NOT `neatlogs.WrapGenAI`).
- Session & end-user identity is per-request — set it with `neatlogs.Identify(ctx, ...)`, NEVER on `Init`. It rides on `ctx`. See step 6.
- Pass the `ctx` from `Identify` / `Trace` / `StartLLMSpan` down into whatever runs the turn — Go propagates identity and parent-span through `context.Context`.
- Never hardcode the API key; use `os.Getenv`.
- **Multiple independent workflows in one service?** `Config.WorkflowName` is process-wide and single-shot. Give each feature its own `workflow` root at its entry point — `neatlogs.StartSpan(ctx, name, "workflow", attribute.String("neatlogs.workflow.name", name))` — so each shows up as a distinct dashboard workflow. See the `neatlogs-multi-workflow` skill.

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
check the Neatlogs dashboard. For `WrapGenAI`, confirm the `llm` span nests under
an auto `workflow` root and carries input/output messages + token usage. For the
explicit helpers, confirm each `StartLLMSpan` / `StartRetrieverSpan` records its
I/O (an empty retriever result is recorded as `"[]"`, not omitted).
