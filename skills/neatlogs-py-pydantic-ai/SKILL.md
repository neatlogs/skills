---
name: neatlogs-py-pydantic-ai
description: Use when adding neatlogs observability to a Python project that uses Pydantic AI (imports `pydantic_ai`, constructs an `Agent`).
metadata:
  author: neatlogs
  language: python
  framework: pydantic-ai
---

# Neatlogs Python Setup — Pydantic AI

This project uses **Pydantic AI** (`pydantic_ai.Agent`). Neatlogs instruments it with **`neatlogs.wrap(agent)`** — wrap each Agent instance once and its run/model/tool calls are auto-traced.

## Core mechanism — `neatlogs.wrap(agent)`

`neatlogs.wrap()` detects the Pydantic AI Agent and patches `run` / `run_sync` / `run_stream` / `iter`, plus installs class-level model (LLM) and tool (TOOL) hooks. Wrapping produces a nested span tree:

```
AGENT  (agent.run / run_sync / run_stream / iter)
  ↳ LLM   (Model.request / request_stream — one per model call)
  ↳ TOOL  (one per tool invocation)
```

Combine it with the manual primitives for your own orchestration code:
- `@neatlogs.span(kind="WORKFLOW"|"CHAIN"|...)` — decorate functions that orchestrate agent calls.
- `@neatlogs.span(kind="EVALUATOR"|"MEMORY")` — decorate ordinary application-owned evaluator or memory functions for automatic input/output and error capture.
- `neatlogs.trace("name", kind=...)` — create the sole span for the only kinds `@span` rejects (`LLM`, `RERANKER`, and `VECTOR_STORE`), or when a raw/custom operation has no decorator boundary or needs direct canonical attributes (for example, a DeepEval callback).
- `neatlogs.log("msg {x}", x=...)` — timestamped steps inside a span.

The wrapper's AGENT/LLM/TOOL spans nest correctly under application-owned orchestration. Never put a same-operation `trace()` inside an `@span`, and never put a manual LLM span around the wrapped agent.

## Steps

1. **Install** → `references/1-install.md`
2. **Add init()** → `references/2-add-init.md`
3. **Set environment variables** → `references/3-set-env.md`
4. **Wrap the Agent with neatlogs.wrap()** → `references/4-wrap-agent.md`
5. **Add @span / trace / log to orchestration** → `references/5-spans-trace-log.md`
6. **Lifecycle (flush/shutdown)** → `references/6-flush-shutdown.md`

## Rules (apply to ALL steps)

- `neatlogs.init()` MUST run BEFORE importing `pydantic_ai` (so class-level hooks patch at the right time). If `load_dotenv()` exists, it runs before `init()`.
- Wrap EVERY `Agent` instance whose runs you want traced: `agent = neatlogs.wrap(agent)`. `wrap()` returns the same instance (also patches in place); use the returned reference.
- `wrap()` already creates the AGENT/LLM/TOOL spans — do NOT also wrap a single `agent.run()` in `@span`/`trace`. Use `@span` only for YOUR surrounding orchestration functions.
- Never hardcode API keys — use `os.getenv()`.
- For managed Neatlogs, omit `endpoint` and `NEATLOGS_ENDPOINT`; the SDK already uses `https://ingest.neatlogs.com`.
- `import neatlogs` at module top level, never inside functions.
- Minimal edits — add wrap()/decorators + imports, don't reformat.

<!-- neatlogs-readiness-v1 -->

## Compatibility and safe-change gate

Before editing, detect the language, package manager, service/framework, installed SDK version, and existing NeatLogs instrumentation without changing files. Read the packaged `.neatlogs/skills-support-v1.json` contract. In a source checkout, use `contracts/skills-support-v1.json`. Reject a missing, invalid, or incompatible contract with its stable public reason code.

The current support contract truthfully marks `neatlogs.doctor/v2` and the correlated backend diagnostic contract as unavailable. Do not substitute the Wizard's bundled Doctor v1 fixture, an implicit `npx` download, package installation, compilation, a local span, HTTP 2xx, or an uncorrelated trace. Stop with `DOCTOR_UNAVAILABLE`, report the detected SDK version and the contract's upgrade guidance, and leave automatic source editing disabled.

A user may explicitly approve a manual documented integration change while this gate is blocked. Show the exact files, commands, and diff first; keep credentials in the user's secret mechanism; run only approved project checks and exercises; and report the result as incomplete until Doctor v2 and a correlated backend receipt pass. Once Doctor v2 is released, change source only for a failed reason code in `safe_fix_allowlist`, only when the check itself marks it fixable, and roll back only this run's edits if validation fails. A second run must produce no unnecessary changes.

## Live completion gate (wizard or standalone coding agent)

This skill does not grant platform access. The marker-aware `get_trace_context` contract must be deployed on the hosted Neatlogs backend, and the installed SDK or exporter must preserve the resource marker; merged source changes or an updated local wizard alone are not proof.

For the representative run, generate two distinct UUIDs: a process marker and an exercise nonce. Append `neatlogs.verification.marker=<marker UUID>` to `OTEL_RESOURCE_ATTRIBUTES`, preserving existing entries and scoping it only to the launched process; do not edit source or persistent configuration, and do not treat either value as a secret. Put the exact token `neatlogs-verification:<nonce UUID>` in a safe representative user request, prompt, or API argument that exercises the real path and should be captured in a persisted span `input_value`. Immediately before the exercise, record the current UTC timestamp. If the coding agent cannot launch a web UI path, tell the user exactly how to start the app with the temporary marker and which nonce token to submit. If the path cannot safely carry a unique captured input, report that blocker and leave verification incomplete.

After the exercised request finishes, flush telemetry and gracefully stop the marked process or relaunch it without the marker before discovery. If marked trace production cannot be quiesced, leave verification incomplete. Then call the already-connected Neatlogs platform MCP with `get_trace_context(verification_marker=<marker UUID>, candidate_offset=0)`. Enumerate offsets from 0 upward, collecting distinct trace IDs until MCP returns `No project trace found` for the next offset. For every candidate, page its complete span set with `get_trace_context(trace_id=<trace_id>, offset=<next_offset>)` until `next_offset` is null. A candidate qualifies only when the exact nonce token appears in a persisted span `input_value`, its top-level `name` and `workflow` plus parentless root span match the exercised path, its `created_at` is not earlier than the recorded timestamp, `root_span_count` is 1, and no span has `synthetic_recovery_root: true`. Never select the first or latest marker match. If no trace qualifies yet, poll every 5 seconds and repeat the full enumeration for up to 2 minutes. Restart a scan if offsets shift and duplicate a trace ID; if a complete distinct scan cannot be obtained, offset 100 still returns a candidate, or zero or multiple traces qualify, report the ambiguity and leave verification incomplete.

Once exactly one trace qualifies, poll that exact `trace_id` every 5 seconds for up to 2 minutes while `status` is `processing` or `finalization_status` is `pending`. If it does not reach `finalized` within that bound, leave verification incomplete. Treat a null or unrecognized `finalization_status` as a hosted-contract blocker. After `finalization_status` is `finalized`, require `trace_context_contract_version: 2`, `verification_ready: true`, `span_payload_complete: true`, `span_tree_complete: true`, and `root_span_count: 1`; otherwise report a hosted-contract or incomplete-payload blocker. Page all spans again and perform two identical full marker-candidate enumerations at least 10 seconds apart to confirm that exactly one trace contains the nonce in both scans. Verify that all `span_count` spans were inspected.

If `get_trace_context` rejects `verification_marker`, `candidate_offset`, `trace_id`, or `offset`, or omits `trace_context_contract_version`, `verification_ready`, `span_payload_complete`, `span_tree_complete`, `root_span_count`, `trace_id`, `name`, `workflow`, `created_at`, `spans[].parent_span_id`, `spans[].input_value`, `status`, `finalization_status`, `next_offset`, or `span_count`, treat the hosted MCP as an old contract: stop, report the hosted deployment blocker, and do not claim verification or use another trace query. If MCP is unavailable, ask the user to configure `https://ingest.neatlogs.com/mcp` with the project key stored as a client secret; never print or request the key in chat, and leave verification incomplete.

- Show user-visible progress for install, edits, checks, restart, runtime verification, and platform confirmation; never print secrets.
- Run existing tests plus the project's build/package/type checks, restart the long-running process, and exercise the actual user-facing wrapped agent path.
- Inspect the full persisted span tree and returned semantic fields, not only a trace-list summary or local debug output. Confirm the nonce-qualified project trace is the fresh run, with one wrapper-owned hierarchy and no duplicate agent/LLM/tool spans. Offline/no-export verification alone is insufficient. Otherwise report the exact blocker and leave the result incomplete.

## Reference

- Combining wrap() with @span/trace/log → `references/5-spans-trace-log.md`
- Span kinds reference → `references/span-kinds.md`
- Sessions & end-users (customer analytics) → `references/sessions-and-end-users.md`
