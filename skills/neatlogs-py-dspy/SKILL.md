---
name: neatlogs-py-dspy
description: Use when adding neatlogs observability to a Python project that uses DSPy (imports `dspy`, defines `dspy.Module`s / signatures).
metadata:
  author: neatlogs
  language: python
  framework: dspy
---

# Neatlogs Python Setup — DSPy

This project uses **DSPy** (`dspy.Module`, `dspy.Predict`, `dspy.ChainOfThought`, `dspy.ReAct`). Neatlogs instruments it with **`neatlogs.wrap(module)`**.

## Core mechanism — `neatlogs.wrap(module)`

`neatlogs.wrap()` installs DSPy class-level hooks (idempotent, global), so passing ANY module instance — including your own `dspy.Module` subclass — patches every module call, nested. Span tree:

```
CHAIN  dspy.Module.__call__   (Predict / ChainOfThought / ReAct / custom — every module call, nested)
  ↳ LLM        dspy.LM.__call__       (the underlying model request)
  ↳ RETRIEVER  dspy.Retrieve.__call__ (if used)
```

Combine with `@neatlogs.span` / `neatlogs.trace` / `neatlogs.log` for your own orchestration. The DSPy CHAIN/LLM spans nest under your manual spans.

## Steps

1. **Install** → `references/1-install.md`
2. **Add init()** → `references/2-add-init.md`
3. **Set environment variables** → `references/3-set-env.md`
4. **Wrap a DSPy module with neatlogs.wrap()** → `references/4-wrap-module.md`
5. **Add @span / trace / log to orchestration** → `references/5-spans-trace-log.md`
6. **Lifecycle (flush/shutdown)** → `references/6-flush-shutdown.md`

## Rules (apply to ALL steps)

- `neatlogs.init()` MUST run BEFORE importing `dspy` (so class hooks patch at the right time). `load_dotenv()` runs before `init()`.
- **Use `neatlogs.wrap(module)`, NOT `instrumentations=["dspy"]`.** `wrap()` patches DSPy's classes directly and works on ANY DSPy version. The `instrumentations=["dspy"]` path uses the OpenInference DSPy instrumentor, which **requires DSPy ≥ 2.6.0 and silently emits no spans on older DSPy** — so prefer `wrap()`, especially when the project pins DSPy < 2.6.
- `neatlogs.wrap(module)` installs GLOBAL DSPy class hooks — calling it once on any module instance traces ALL module/LM calls. Wrapping the top-level pipeline module is enough.
- `wrap()` returns the module unchanged; you can keep using your existing variable.
- Do NOT wrap a single module call in `@span`/`trace` — the CHAIN span is created by the hook. Use `@span` for YOUR orchestration only.
- The DSPy hooks own module, LLM, and retriever spans. Do NOT add a manual `trace(kind="LLM")`, LLM decorator, or provider instrumentor around DSPy-owned model calls.
- Never hardcode API keys — use `os.getenv()`.
- For managed Neatlogs, omit `endpoint` and `NEATLOGS_ENDPOINT`; the SDK already uses `https://ingest.neatlogs.com`.
- `import neatlogs` at module top level.

## Live completion gate (wizard or standalone coding agent)

This skill does not grant platform access. The marker-aware `get_trace_context` contract must be deployed on the hosted Neatlogs backend, and the installed SDK or exporter must preserve the resource marker; merged source changes or an updated local wizard alone are not proof.

For the representative run, generate two distinct UUIDs: a process marker and an exercise nonce. Append `neatlogs.verification.marker=<marker UUID>` to `OTEL_RESOURCE_ATTRIBUTES`, preserving existing entries and scoping it only to the launched process; do not edit source or persistent configuration, and do not treat either value as a secret. Put the exact token `neatlogs-verification:<nonce UUID>` in a safe representative user request, prompt, or API argument that exercises the real path and should be captured in a persisted span `input_value`. Immediately before the exercise, record the current UTC timestamp. If the coding agent cannot launch a web UI path, tell the user exactly how to start the app with the temporary marker and which nonce token to submit. If the path cannot safely carry a unique captured input, report that blocker and leave verification incomplete.

After the exercised request finishes, flush telemetry and gracefully stop the marked process or relaunch it without the marker before discovery. If marked trace production cannot be quiesced, leave verification incomplete. Then call the already-connected Neatlogs platform MCP with `get_trace_context(verification_marker=<marker UUID>, candidate_offset=0)`. Enumerate offsets from 0 upward, collecting distinct trace IDs until MCP returns `No project trace found` for the next offset. For every candidate, page its complete span set with `get_trace_context(trace_id=<trace_id>, offset=<next_offset>)` until `next_offset` is null. A candidate qualifies only when the exact nonce token appears in a persisted span `input_value`, its top-level `name` and `workflow` plus parentless root span match the exercised path, its `created_at` is not earlier than the recorded timestamp, `root_span_count` is 1, and no span has `synthetic_recovery_root: true`. Never select the first or latest marker match. If no trace qualifies yet, poll every 5 seconds and repeat the full enumeration for up to 2 minutes. Restart a scan if offsets shift and duplicate a trace ID; if a complete distinct scan cannot be obtained, offset 100 still returns a candidate, or zero or multiple traces qualify, report the ambiguity and leave verification incomplete.

Once exactly one trace qualifies, poll that exact `trace_id` every 5 seconds for up to 2 minutes while `status` is `processing` or `finalization_status` is `pending`. If it does not reach `finalized` within that bound, leave verification incomplete. Treat a null or unrecognized `finalization_status` as a hosted-contract blocker. After `finalization_status` is `finalized`, require `trace_context_contract_version: 2`, `verification_ready: true`, `span_payload_complete: true`, `span_tree_complete: true`, and `root_span_count: 1`; otherwise report a hosted-contract or incomplete-payload blocker. Page all spans again and perform two identical full marker-candidate enumerations at least 10 seconds apart to confirm that exactly one trace contains the nonce in both scans. Verify that all `span_count` spans were inspected.

If `get_trace_context` rejects `verification_marker`, `candidate_offset`, `trace_id`, or `offset`, or omits `trace_context_contract_version`, `verification_ready`, `span_payload_complete`, `span_tree_complete`, `root_span_count`, `trace_id`, `name`, `workflow`, `created_at`, `spans[].parent_span_id`, `spans[].input_value`, `status`, `finalization_status`, `next_offset`, or `span_count`, treat the hosted MCP as an old contract: stop, report the hosted deployment blocker, and do not claim verification or use another trace query. If MCP is unavailable, ask the user to configure `https://ingest.neatlogs.com/mcp` with the project key stored as a client secret; never print or request the key in chat, and leave verification incomplete.

- Show user-visible progress for install, edits, checks, restart, runtime verification, and platform confirmation; never print secrets.
- Run existing tests plus the project's build/package/type checks, restart the long-running process, and exercise the actual user-facing wrapped path.
- Inspect the full persisted span tree and returned semantic fields, not only a trace-list summary or local debug output. Confirm the nonce-qualified project trace is the fresh run, with one wrapper-owned hierarchy and no duplicate module/LLM spans. Offline/no-export verification alone is insufficient. Otherwise report the exact blocker and leave the result incomplete.

## Reference
- Combining wrap() with @span/trace/log → `references/5-spans-trace-log.md`
- Span kinds reference → `references/span-kinds.md`
- Sessions & end-users (customer analytics via identify()) → `references/sessions-and-end-users.md`
