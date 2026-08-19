---
name: neatlogs-go
description: Use when adding neatlogs observability to a Go project — Google Gemini (genai), direct LLM/provider calls, retrieval, service boundaries, or custom code. Covers Init, WrapGenAI, explicit span helpers (StartLLMSpan / StartRetrieverSpan / StartToolSpanFromHeaders), Trace, and Identify (sessions & end-users).
metadata:
  author: neatlogs
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
Export is OTLP/HTTP to the managed Neatlogs cloud.

## Transport selection

Use this SDK for Go. Neatlogs also has SDKs for Python and TypeScript/Node.js. For a language without a supported Neatlogs SDK, default to the dependency-free HTTP ingest endpoint `POST /v1/trace`; if that project already emits OpenTelemetry, OTLP/gRPC is also supported. Use the `neatlogs-ingest` skill for the complete HTTP and gRPC contracts. Do not confuse `/v1/trace` nested JSON with the `/v1/traces` OTLP/HTTP protobuf route.

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
   `WrapGenAI` owns the canonical LLM span. Do not surround calls through `gc`
   with `Trace`, `StartSpan(..., "llm")`, or `StartLLMSpan`.
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
- **Use exactly one capture owner per model call.** `WrapGenAI` owns Gemini calls made through the wrapped client. Never add `Trace`, an `llm` `StartSpan`, or `StartLLMSpan` around those calls. Use `StartLLMSpan` only for a direct or unsupported provider call that has no supported wrapper.
- Session & end-user identity is per-request — set it with `neatlogs.Identify(ctx, ...)`, NEVER on `Init`. It rides on `ctx`. See step 6.
- Pass the `ctx` from `Identify` / `Trace` / `StartLLMSpan` down into whatever runs the turn — Go propagates identity and parent-span through `context.Context`.
- Never hardcode the API key; use `os.Getenv`.
- For managed Neatlogs, omit `Endpoint` and `NEATLOGS_ENDPOINT`; the SDK already exports to `https://ingest.neatlogs.com`. Preserve an explicit endpoint only for a confirmed self-hosted deployment.
- **Multiple independent workflows in one service?** `Config.WorkflowName` is process-wide and single-shot. At each independent feature entry point, start a parentless `workflow` span with the canonical per-root override — `neatlogs.StartSpan(ctx, name, "workflow", attribute.String("neatlogs.workflow.name", name))` — so each fresh request/job becomes a distinct dashboard workflow. See the `neatlogs-multi-workflow` skill.

## `neatlogs.Init()` Config Reference

| Field | Type | Default | Description |
|---|---|---|---|
| `APIKey` | `string` | `NEATLOGS_API_KEY` env | Auth key. Empty (after env fallback) → export disabled, spans dropped |
| `Endpoint` | `string` | `NEATLOGS_ENDPOINT`, then `https://ingest.neatlogs.com` | Self-hosted OTLP/HTTP base URL. Omit for managed Neatlogs |
| `WorkflowName` | `string` | caller source path, then `neatlogs-app` | Labels this service/run |
| `Tags` | `[]string` | `nil` | Attached to every span as a resource attribute |
| `Debug` | `bool` | `false` | Verbose diagnostics on stderr |
| `DisableExport` | `bool` | `false` | Drop all spans instead of sending (useful in tests) |

> Note: `Init` has NO session / end-user field. Those are per-request — see `Identify` (step 6). Config carries no operator id either; identity is set at the trace boundary.

`neatlogs.Version` is exported (const) and stamped on every trace as the `service.version` resource attribute + the instrumentation-scope version — useful when pinning down which SDK build emitted a span.

## Verify

Run the repository's existing checks. At minimum, run `go test ./...` and
`go build ./...`; run `go mod tidy` first when dependencies changed. Restart the
real server, worker, or binary after changing startup instrumentation, then
exercise the actual instrumented path. Run with `Debug: true` and confirm export
succeeds.

Check the target Neatlogs project, not merely local debug output. For
`WrapGenAI`, confirm exactly one canonical `llm` span per call, nested under the
expected `workflow`, with input/output messages and token usage. For explicit
helpers, confirm each `StartLLMSpan` / `StartRetrieverSpan` records its I/O (an
empty retriever result is recorded as `"[]"`, not omitted).
`StartRetrieverSpan` emits the canonical `neatlogs.retriever.*` namespace;
never emit the legacy `neatlogs.retrieval.*` spelling from new code.

## Live completion gate (wizard or standalone coding agent)

Show concise, secret-free progress for install, edits, checks/build, process
restart, runtime exercise, and platform confirmation. This skill does not grant
platform access. The marker-aware `get_trace_context` contract must be deployed on the hosted Neatlogs backend; a merged backend change or updated local wizard alone is not proof.

For the representative run, generate a UUID and append `neatlogs.verification.marker=<UUID>` to `OTEL_RESOURCE_ATTRIBUTES`, preserving existing entries. Scope it only to the launched process: do not edit source or persistent configuration, and do not treat the marker as a secret. Immediately before exercising the real path, record the current UTC timestamp. If the coding agent cannot launch a web UI path, tell the user exactly how to start the app with that temporary environment value, then continue verification against the same marker.

After the run, call the already-connected Neatlogs platform MCP's existing `get_trace_context(verification_marker=<same UUID>)` directly; make no preliminary MCP discovery calls and never fall back to the latest trace if the marker is absent; report that exact blocker and leave verification incomplete. While `status` is `processing` or `finalization_status` is `pending`, poll the same trace with `get_trace_context(trace_id=<trace_id>)`. Only after `finalization_status` is `finalized`, page with `get_trace_context(trace_id=<trace_id>, offset=<next_offset>)` until `next_offset` is null, and verify that all `span_count` spans were inspected.

If `get_trace_context` rejects `verification_marker`, `trace_id`, or `offset`, or omits `status`, `finalization_status`, `next_offset`, or `span_count`, treat the hosted MCP as an old contract: stop, report the hosted deployment blocker, and do not claim verification or use another trace query.

If platform MCP is unavailable, ask the user to connect it through their coding
agent using the Neatlogs MCP server (`https://ingest.neatlogs.com/mcp`) or the
`npx @neatlogs/wizard mcp --api-key <PROJECT_KEY>` command. The project key must
go through the client's secret configuration; never print it or ask the user to
paste it into chat. If access cannot be established, leave verification
incomplete rather than claiming success.

Do not report success until all of these are true:

1. The project checks and build pass.
2. The process that loads `Init` and the wrapper/helpers has been restarted.
3. The real user path has been exercised, not just a synthetic import check.
4. The marker-matched project trace is the fresh run. Its full persisted span tree and
   attributes show exactly one canonical span per operation and no duplicate
   LLM span; a trace-list summary is not enough.

An offline or `DisableExport: true` check is useful for diagnosis but is not
proof that ingestion works. If any step cannot be completed, report the exact
command, observation, and blocker; leave the setup explicitly incomplete.
