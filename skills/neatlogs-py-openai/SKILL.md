---
name: neatlogs-py-openai
description: Use when adding neatlogs observability to a Python project that calls LLM provider SDKs directly (OpenAI, Anthropic, Google GenAI, Groq, etc.) and uses no agent framework.
metadata:
  author: neatlogs
  language: python
  framework: openai
---

# Neatlogs Python Setup — Direct LLM SDK (OpenAI / Anthropic / Google GenAI / …)

This project calls LLM APIs directly (e.g., `client.chat.completions.create()`). There is no agent framework managing tools or chains. Wrap supported clients once; decorate only the application's own orchestration and custom tools.

## Instrumentation — pick the path that matches the provider

There are two equivalent ways to capture LLM/embedding calls. **Prefer `neatlogs.wrap()`** — it is per-instance, explicit, and needs no global config.

### Path A (PREFERRED) — `neatlogs.wrap(client)` for OpenAI / Anthropic / Google GenAI

`neatlogs.wrap()` detects the client type and patches its LLM-relevant resources in place, returning the same instance:

```python
import neatlogs
from openai import OpenAI

client = neatlogs.wrap(OpenAI())        # chat, responses, embeddings, images, audio … all traced
client.chat.completions.create(...)     # → LLM span (model, tokens, latency)
client.embeddings.create(...)           # → EMBEDDING span
```

Supported by `wrap()`: `OpenAI` / `AsyncOpenAI`, `Anthropic` / `AsyncAnthropic`, `google.genai.Client`. Same call for all three — it auto-routes by type. When you use `wrap()`, do NOT pass `instrumentations=` for that provider.

### Path B (fallback) — `instrumentations=[...]` for providers `wrap()` doesn't cover

`wrap()` does NOT support Groq, Cohere, Bedrock, Mistral, Together, LiteLLM, etc. For those, pass the provider name to `init(instrumentations=[...])` (the global auto-instrumentor):

| Provider SDK | Path |
|---|---|
| OpenAI / Anthropic / Google GenAI | `neatlogs.wrap(client)` (Path A) |
| Groq | `init(instrumentations=["groq"])` |
| Cohere | `init(instrumentations=["cohere"])` |
| Bedrock | `init(instrumentations=["bedrock"])` |
| Mistral | `init(instrumentations=["mistralai"])` |
| Together | `init(instrumentations=["together"])` |
| LiteLLM | `init(instrumentations=["litellm"])` |

Mixing is fine: e.g. wrap an OpenAI client AND `init(instrumentations=["groq"])` if the app uses both. Never list a provider in `instrumentations=[]` AND `wrap()` the same client — that double-fires and produces duplicate spans.

## Combine with manual primitives

- `@neatlogs.span(kind="WORKFLOW"|"CHAIN"|"TOOL"|...)` — decorate orchestration / tool functions.
- `neatlogs.trace("name", kind="LLM", ...)` — create the canonical LLM span only for an unsupported/raw call that has no wrapper or instrumentor.
- `neatlogs.log("msg {x}", x=…)` — timestamped steps inside a span.

The captured LLM/EMBEDDING spans nest under your orchestration spans. Do not add a second manual LLM layer around them.

## Steps

1. **Install SDK** → `references/1-install-sdk.md`
2. **Add init()** → `references/2-add-init.md`
3. **Set environment variables** → `references/3-set-env.md`
4. **Wrap the LLM client(s)** → `references/4-wrap-client.md`
5. **Decorate orchestration functions** → `references/5-decorate-functions.md`
6. **Verify LLM calls have exactly one capture owner** → `references/6-wrap-llm-calls.md`
7. **Decorate tool functions** → `references/7-decorate-tools.md`
7.5. **Embeddings: wrapped/instrumented = automatic; custom = decorate** → `references/7.5-embeddings.md`
8. **Add flush/shutdown** → `references/8-flush-shutdown.md`

## Rules (apply to ALL steps)

- `neatlogs.init()` MUST execute BEFORE the LLM library is imported and BEFORE any client is constructed.
- If `load_dotenv()` exists, it MUST run BEFORE `neatlogs.init()`.
- Prefer `neatlogs.wrap(client)` for OpenAI/Anthropic/Google GenAI; use `init(instrumentations=[...])` only for providers `wrap()` doesn't support. Never both for the same client.
- Wrap EVERY supported LLM client whose calls you want traced: `client = neatlogs.wrap(client)`. Use the returned reference.
- Never hardcode API keys in source. Use `os.getenv()`.
- For managed Neatlogs, omit `endpoint` and `NEATLOGS_ENDPOINT`; the SDK already uses `https://ingest.neatlogs.com`.
- Add imports ONLY for what a file actually uses:
  - File calls `neatlogs.wrap(...)` / `neatlogs.span(...)` / a manual raw-call `neatlogs.trace(...)` → add `import neatlogs`.
- When present, `import neatlogs` goes at module top level, never inside functions.
- `@neatlogs.span()` goes BELOW framework decorators (`@retry`, `@app.route`) — closest to `def`.
- Minimal edits only. Add wrap()/decorators + imports. Do not reformat, add comments, or refactor.

## What's auto-captured (DO NOT also manually trace)

Once a client is `wrap()`'d (or its provider is in `instrumentations=[]`), these are auto-captured — do not add a TOOL/EMBEDDING span around them:
- `client.chat.completions.create()` / `client.responses.create()` → LLM span (model, tokens, latency, finish reason)
- `client.messages.create()` (Anthropic) → LLM span
- `client.models.generate_content()` (Google GenAI) → LLM span
- `client.embeddings.create()` → EMBEDDING span
- Streaming variants

You may add WORKFLOW/CHAIN/AGENT spans around genuine multi-step orchestration. Do NOT add `neatlogs.trace(kind="LLM")` around any wrapped or instrumented provider call; the automatic span is canonical.

## Doctor gate

Before editing, run this read-only preflight from the application root:

```bash
npx --yes @neatlogs/wizard@latest doctor --local --json --install-dir .
```

Require `doctor_version: 1` and `schema_version: 2`. Treat `application_exercised: false` and `capture_scope: "wizard_sdk_fixture"` literally: local doctor validates static target configuration plus the wizard's normalized in-memory SDK fixture; it is not proof that this application's runtime or the backend worked.

Only remediate a failed check when `fixable: true`: `INSTRUMENTOR_NOT_ACTIVE` means install/initialize using this skill; `ATTRIBUTE_CONFLICT` means apply only the conflict named in the check; `MISSING_API_KEY` means configure the key through the user's secret/environment mechanism, never source or chat. Do not edit for any other code or for warnings such as `PROJECT_OWNERSHIP_AMBIGUOUS`; report the exact check instead.

After the project checks/build and a real-path exercise, run `npx --yes @neatlogs/wizard@latest doctor --probe --json --install-dir .` with `NEATLOGS_API_KEY` supplied through the process environment. If it returns `BACKEND_DIAGNOSTIC_UNAVAILABLE`, no probe was sent: report that deployment blocker and leave diagnostic-stage verification incomplete. Never substitute a local span log, package installation, or an uncorrelated latest trace for doctor/backend evidence. The marker-correlated platform completion gate below remains a separate persistence check.

+## Live completion gate (wizard or standalone coding agent)

This skill does not grant platform access. The marker-aware `get_trace_context` contract must be deployed on the hosted Neatlogs backend, and the installed SDK or exporter must preserve the resource marker; merged source changes or an updated local wizard alone are not proof.

For the representative run, generate two distinct UUIDs: a process marker and an exercise nonce. Append `neatlogs.verification.marker=<marker UUID>` to `OTEL_RESOURCE_ATTRIBUTES`, preserving existing entries and scoping it only to the launched process; do not edit source or persistent configuration, and do not treat either value as a secret. Put the exact token `neatlogs-verification:<nonce UUID>` in a safe representative user request, prompt, or API argument that exercises the real path and should be captured in a persisted span `input_value`. Immediately before the exercise, record the current UTC timestamp. If the coding agent cannot launch a web UI path, tell the user exactly how to start the app with the temporary marker and which nonce token to submit. If the path cannot safely carry a unique captured input, report that blocker and leave verification incomplete.

After the exercised request finishes, flush telemetry and gracefully stop the marked process or relaunch it without the marker before discovery. If marked trace production cannot be quiesced, leave verification incomplete. Then call the already-connected Neatlogs platform MCP with `get_trace_context(verification_marker=<marker UUID>, candidate_offset=0)`. Enumerate offsets from 0 upward, collecting distinct trace IDs until MCP returns `No project trace found` for the next offset. For every candidate, page its complete span set with `get_trace_context(trace_id=<trace_id>, offset=<next_offset>)` until `next_offset` is null. A candidate qualifies only when the exact nonce token appears in a persisted span `input_value`, its top-level `name` and `workflow` plus parentless root span match the exercised path, its `created_at` is not earlier than the recorded timestamp, `root_span_count` is 1, and no span has `synthetic_recovery_root: true`. Never select the first or latest marker match. If no trace qualifies yet, poll every 5 seconds and repeat the full enumeration for up to 2 minutes. Restart a scan if offsets shift and duplicate a trace ID; if a complete distinct scan cannot be obtained, offset 100 still returns a candidate, or zero or multiple traces qualify, report the ambiguity and leave verification incomplete.

Once exactly one trace qualifies, poll that exact `trace_id` every 5 seconds for up to 2 minutes while `status` is `processing` or `finalization_status` is `pending`. If it does not reach `finalized` within that bound, leave verification incomplete. Treat a null or unrecognized `finalization_status` as a hosted-contract blocker. After `finalization_status` is `finalized`, require `trace_context_contract_version: 2`, `verification_ready: true`, `span_payload_complete: true`, `span_tree_complete: true`, and `root_span_count: 1`; otherwise report a hosted-contract or incomplete-payload blocker. Page all spans again and perform two identical full marker-candidate enumerations at least 10 seconds apart to confirm that exactly one trace contains the nonce in both scans. Verify that all `span_count` spans were inspected.

If `get_trace_context` rejects `verification_marker`, `candidate_offset`, `trace_id`, or `offset`, or omits `trace_context_contract_version`, `verification_ready`, `span_payload_complete`, `span_tree_complete`, `root_span_count`, `trace_id`, `name`, `workflow`, `created_at`, `spans[].parent_span_id`, `spans[].input_value`, `status`, `finalization_status`, `next_offset`, or `span_count`, treat the hosted MCP as an old contract: stop, report the hosted deployment blocker, and do not claim verification or use another trace query. If MCP is unavailable, ask the user to configure `https://ingest.neatlogs.com/mcp` with the project key stored as a client secret; never print or request the key in chat, and leave verification incomplete.

- Print concise user-visible progress before and after install, edits, dependency/import checks, server restart, runtime verification, and platform confirmation. Never print secrets.
- Run the project's existing tests plus its build/package/type checks after editing. Restart the long-running process so startup instrumentation is actually loaded.
- Exercise the actual user-facing instrumented path. Inspect the full persisted span tree and returned semantic fields, not only a trace-list summary or local debug output. Confirm the nonce-qualified project trace is the fresh run, with one canonical span per operation and no duplicate LLM/tool/agent spans. An offline/no-export verifier is insufficient by itself.
- Do not claim completion until all applicable checks pass. If runtime or ingestion cannot be confirmed, report the exact blocker and leave the result incomplete.

## Reference

- Span kinds → `references/span-kinds.md`
- LLM call patterns → `references/llm-call-patterns.md`
- Sessions & end-users → `references/sessions-and-end-users.md`
