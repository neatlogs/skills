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

<!-- neatlogs-readiness-v1 -->

## Compatibility and safe-change gate

Before editing, detect the language, package manager, service/framework, installed SDK version, and existing NeatLogs instrumentation without changing files. Read the packaged `.neatlogs/skills-support-v1.json` contract. In a source checkout, use `contracts/skills-support-v1.json`. Reject a missing, invalid, or incompatible contract with its stable public reason code.

The current support contract truthfully marks `neatlogs.doctor/v2` and the correlated backend diagnostic contract as unavailable. Do not substitute the Wizard's bundled Doctor v1 fixture, an implicit `npx` download, package installation, compilation, a local span, HTTP 2xx, or an uncorrelated trace. Stop with `DOCTOR_UNAVAILABLE`, report the detected SDK version and the contract's upgrade guidance, and leave automatic source editing disabled.

A user may explicitly approve a manual documented integration change while this gate is blocked. Show the exact files, commands, and diff first; keep credentials in the user's secret mechanism; run only approved project checks and exercises; and report the result as incomplete until Doctor v2 and a correlated backend receipt pass. Once Doctor v2 is released, change source only for a failed reason code in `safe_fix_allowlist`, only when the check itself marks it fixable, and roll back only this run's edits if validation fails. A second run must produce no unnecessary changes.

## Live completion gate (wizard or standalone coding agent)

Show concise, secret-free progress for install, edits, checks/build, process
restart, runtime exercise, and platform confirmation. This skill does not grant
platform access. The marker-aware `get_trace_context` contract must be deployed on the hosted Neatlogs backend, and the installed SDK or exporter must preserve the resource marker; merged source changes or an updated local wizard alone are not proof.

For the representative run, generate two distinct UUIDs: a process marker and an exercise nonce. Append `neatlogs.verification.marker=<marker UUID>` to `OTEL_RESOURCE_ATTRIBUTES`, preserving existing entries and scoping it only to the launched process; do not edit source or persistent configuration, and do not treat either value as a secret. Put the exact token `neatlogs-verification:<nonce UUID>` in a safe representative user request, prompt, or API argument that exercises the real path and should be captured in a persisted span `input_value`. Immediately before the exercise, record the current UTC timestamp. If the coding agent cannot launch a web UI path, tell the user exactly how to start the app with the temporary marker and which nonce token to submit. If the path cannot safely carry a unique captured input, report that blocker and leave verification incomplete.

After the exercised request finishes, flush telemetry and gracefully stop the marked process or relaunch it without the marker before discovery. If marked trace production cannot be quiesced, leave verification incomplete. Then call the already-connected Neatlogs platform MCP with `get_trace_context(verification_marker=<marker UUID>, candidate_offset=0)`. Enumerate offsets from 0 upward, collecting distinct trace IDs until MCP returns `No project trace found` for the next offset. For every candidate, page its complete span set with `get_trace_context(trace_id=<trace_id>, offset=<next_offset>)` until `next_offset` is null. A candidate qualifies only when the exact nonce token appears in a persisted span `input_value`, its top-level `name` and `workflow` plus parentless root span match the exercised path, its `created_at` is not earlier than the recorded timestamp, `root_span_count` is 1, and no span has `synthetic_recovery_root: true`. Never select the first or latest marker match. If no trace qualifies yet, poll every 5 seconds and repeat the full enumeration for up to 2 minutes. Restart a scan if offsets shift and duplicate a trace ID; if a complete distinct scan cannot be obtained, offset 100 still returns a candidate, or zero or multiple traces qualify, report the ambiguity and leave verification incomplete.

Once exactly one trace qualifies, poll that exact `trace_id` every 5 seconds for up to 2 minutes while `status` is `processing` or `finalization_status` is `pending`. If it does not reach `finalized` within that bound, leave verification incomplete. Treat a null or unrecognized `finalization_status` as a hosted-contract blocker. After `finalization_status` is `finalized`, require `trace_context_contract_version: 2`, `verification_ready: true`, `span_payload_complete: true`, `span_tree_complete: true`, and `root_span_count: 1`; otherwise report a hosted-contract or incomplete-payload blocker. Page all spans again and perform two identical full marker-candidate enumerations at least 10 seconds apart to confirm that exactly one trace contains the nonce in both scans. Verify that all `span_count` spans were inspected.

If `get_trace_context` rejects `verification_marker`, `candidate_offset`, `trace_id`, or `offset`, or omits `trace_context_contract_version`, `verification_ready`, `span_payload_complete`, `span_tree_complete`, `root_span_count`, `trace_id`, `name`, `workflow`, `created_at`, `spans[].parent_span_id`, `spans[].input_value`, `status`, `finalization_status`, `next_offset`, or `span_count`, treat the hosted MCP as an old contract: stop, report the hosted deployment blocker, and do not claim verification or use another trace query.

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
4. The nonce-qualified project trace is the fresh run. Its full persisted span tree and
   attributes show exactly one canonical span per operation and no duplicate
   LLM span; a trace-list summary is not enough.

An offline or `DisableExport: true` check is useful for diagnosis but is not
proof that ingestion works. If any step cannot be completed, report the exact
command, observation, and blocker; leave the setup explicitly incomplete.
