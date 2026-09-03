---
name: neatlogs-ts-openai
description: Use when adding neatlogs observability to a TypeScript/Node.js project that calls LLM provider SDKs directly (OpenAI, Anthropic, Google GenAI, Bedrock) and uses no agent framework.
metadata:
  author: neatlogs
  language: typescript
  framework: openai
---

# Neatlogs TypeScript Setup — Direct LLM SDK (OpenAI / Anthropic / Google / Bedrock)

This project calls an LLM provider SDK directly (no agent framework). Neatlogs instruments supported providers with an **explicit `wrap*` helper applied to the client instance**. The wrapper is the sole owner of each provider LLM span. Add `span()` only around your own multi-step orchestration; use a manual `trace({ kind: 'LLM' })` only for an unsupported/raw LLM call that has no wrapper, handler, hook, processor, or instrumentor.

> **`init({ instrumentations: [...] })` throws.** Every provider key is rejected — the underlying instrumentors drive the **global** OpenTelemetry context, which Neatlogs' private provider cannot isolate from a co-tenant tracer (Datadog, etc.). The thrown error names the helper to use instead. Older guidance offered the key as a zero-touch path — that is gone.

## Core mechanism

1. `await init({ apiKey })` once at startup — with NO `instrumentations` key.
2. Wrap each provider client at its construction site: `const client = wrapOpenAI(new OpenAI())`.
3. Call the wrapped client normally. Optionally use `span({ kind: 'WORKFLOW' }, fn)` to group a multi-step user-facing feature. Do **not** add `trace({ kind:'LLM' })` around wrapped calls.

## Provider → helper

| SDK | Helper | Import from |
|---|---|---|
| OpenAI | `wrapOpenAI(new OpenAI())` | `neatlogs/openai` |
| Azure OpenAI | `wrapAzureOpenAI(client)` | `neatlogs/azure-openai` |
| Anthropic | `wrapAnthropic(new Anthropic())` | `neatlogs/anthropic` |
| Google GenAI (Gemini / AI Studio) | `wrapGoogleGenAI(new GoogleGenAI({ apiKey }))` | `neatlogs/google-genai` |
| Google GenAI (Vertex mode) | `wrapVertexAI(client)` | `neatlogs/vertex-ai` |
| AWS Bedrock | `wrapBedrock(new BedrockRuntimeClient({}))` | `neatlogs/bedrock` |

All of these are also re-exported from the root `neatlogs` entry. Wrap once, at construction, and use the returned client everywhere — then call it exactly as normal (`gc.models.generateContent(...)`, `client.chat.completions.create(...)`). Because the helpers patch the **instance** and not the module, there is **no import-order rule**: plain static imports are correct and dynamic `import()` buys nothing.

A provider with no helper (Cohere, Groq, Mistral, Ollama, Together, raw `fetch`) is **not** traced — instrument those calls with a manual `trace({ kind: 'LLM' })` span.

## Steps

1. **Install** → `references/1-install.md`
2. **Add init() + wrap the client** → `references/2-add-init.md`
3. **Set environment variables** → `references/3-set-env.md`
4. **Wrap multi-step orchestration; verify provider calls are not double-wrapped** → `references/4-spans-and-traces.md`
5. **Lifecycle (flush/shutdown)** → `references/5-lifecycle.md`

## Rules (apply to ALL steps)

- `await init(...)` runs once at startup. Import order does NOT matter — the helpers patch the client instance, so static imports of the LLM SDK are fine and no dynamic `import()` is needed.
- NEVER pass `instrumentations: [...]` to `init()` — it **throws** for every provider key. Wrap the client instead.
- Every provider client the code constructs must be wrapped; an unwrapped client is silently untraced.
- All lifecycle calls are async: `await init/flush/shutdown`.
- The wrapper captures the provider LLM call (input/output, model, tokens, latency) and auto-opens a WORKFLOW root if the call would be parentless. It is the canonical LLM span.
- NEVER put `trace({ kind:'LLM' })`, `span()`, or another provider/framework instrumentor around a single wrapped call. That creates redundant instrumentation. A WORKFLOW/CHAIN/AGENT span may enclose several wrapped calls to represent real orchestration.
- Use manual `trace({ kind:'LLM' })` only for a provider or raw HTTP call that no supported capture layer owns. Manual spans must record their own input, output, model, usage, and errors.
- Never hardcode API keys — use `process.env`.
- For managed Neatlogs, omit `endpoint`, `baseUrl`, and `NEATLOGS_ENDPOINT`; the SDK already uses `https://ingest.neatlogs.com`.

## Live completion gate (wizard or standalone coding agent)

This skill does not grant platform access. The marker-aware `get_trace_context` contract must be deployed on the hosted Neatlogs backend, and the installed SDK or exporter must preserve the resource marker; merged source changes or an updated local wizard alone are not proof.

For the representative run, generate two distinct UUIDs: a process marker and an exercise nonce. Append `neatlogs.verification.marker=<marker UUID>` to `OTEL_RESOURCE_ATTRIBUTES`, preserving existing entries and scoping it only to the launched process; do not edit source or persistent configuration, and do not treat either value as a secret. Put the exact token `neatlogs-verification:<nonce UUID>` in a safe representative user request, prompt, or API argument that exercises the real path and should be captured in a persisted span `input_value`. Immediately before the exercise, record the current UTC timestamp. If the coding agent cannot launch a web UI path, tell the user exactly how to start the app with the temporary marker and which nonce token to submit. If the path cannot safely carry a unique captured input, report that blocker and leave verification incomplete.

After the exercised request finishes, flush telemetry and gracefully stop the marked process or relaunch it without the marker before discovery. If marked trace production cannot be quiesced, leave verification incomplete. Then call the already-connected Neatlogs platform MCP with `get_trace_context(verification_marker=<marker UUID>, candidate_offset=0)`. Enumerate offsets from 0 upward, collecting distinct trace IDs until MCP returns `No project trace found` for the next offset. For every candidate, page its complete span set with `get_trace_context(trace_id=<trace_id>, offset=<next_offset>)` until `next_offset` is null. A candidate qualifies only when the exact nonce token appears in a persisted span `input_value`, its top-level `name` and `workflow` plus parentless root span match the exercised path, its `created_at` is not earlier than the recorded timestamp, `root_span_count` is 1, and no span has `synthetic_recovery_root: true`. Never select the first or latest marker match. If no trace qualifies yet, poll every 5 seconds and repeat the full enumeration for up to 2 minutes. Restart a scan if offsets shift and duplicate a trace ID; if a complete distinct scan cannot be obtained, offset 100 still returns a candidate, or zero or multiple traces qualify, report the ambiguity and leave verification incomplete.

Once exactly one trace qualifies, poll that exact `trace_id` every 5 seconds for up to 2 minutes while `status` is `processing` or `finalization_status` is `pending`. If it does not reach `finalized` within that bound, leave verification incomplete. Treat a null or unrecognized `finalization_status` as a hosted-contract blocker. After `finalization_status` is `finalized`, require `trace_context_contract_version: 2`, `verification_ready: true`, `span_payload_complete: true`, `span_tree_complete: true`, and `root_span_count: 1`; otherwise report a hosted-contract or incomplete-payload blocker. Page all spans again and perform two identical full marker-candidate enumerations at least 10 seconds apart to confirm that exactly one trace contains the nonce in both scans. Verify that all `span_count` spans were inspected.

If `get_trace_context` rejects `verification_marker`, `candidate_offset`, `trace_id`, or `offset`, or omits `trace_context_contract_version`, `verification_ready`, `span_payload_complete`, `span_tree_complete`, `root_span_count`, `trace_id`, `name`, `workflow`, `created_at`, `spans[].parent_span_id`, `spans[].input_value`, `status`, `finalization_status`, `next_offset`, or `span_count`, treat the hosted MCP as an old contract: stop, report the hosted deployment blocker, and do not claim verification or use another trace query. If MCP is unavailable, ask the user to configure `https://ingest.neatlogs.com/mcp` with the project key stored as a client secret; never print or request the key in chat, and leave verification incomplete.

- Print a concise, user-visible progress update before and after install, code changes, build, restart, runtime verification, and platform confirmation. Never print secrets.
- Run the project's existing build/typecheck/test commands with its detected package manager after editing. Source inspection alone is not verification.
- For servers and startup hooks, build and start a fresh process after instrumentation changes; hot reload is not proof that a newly-added startup file loaded. Exercise the actual instrumented route, action, or entry point.
- Run a safe bounded verification through the real instrumented entry point. Inspect the full persisted span tree and returned semantic fields, not only a trace-list summary or local debug output. Confirm the nonce-qualified project trace is the fresh run and has one canonical span per operation, expected input/output, and no duplicate LLM spans. An offline verifier that disables export is not sufficient by itself.
- Do not report completion until every applicable check passes. If execution or ingestion cannot be verified, report the run as incomplete with the exact blocker and next command; never claim success from edits alone.

## Reference

- **Next.js setup (init via dynamic import in instrumentation.ts)** → `references/nextjs.md` — REQUIRED if the project is a Next.js app, else the server 500s with `Can't resolve 'crypto'` and emits no traces.
- Custom span()/trace() deep dive → `references/decorators-and-traces.md`
- Sessions & end-users (per-turn `identify()`) → `references/sessions-and-end-users.md`
- Troubleshooting → `references/troubleshooting.md`
