---
name: neatlogs-py-agno
description: Use when adding neatlogs observability to a Python project that uses the Agno agent framework (imports `agno`, constructs Agno `Agent`s).
metadata:
  author: neatlogs
  language: python
  framework: agno
---

# Neatlogs Python Setup — Agno

This project uses **Agno** (`agno.agent.Agent`, `Team`, `Workflow`). Neatlogs instruments it with **`neatlogs.wrap(agent)`**.

## Core mechanism — `neatlogs.wrap(entity)`

`neatlogs.wrap()` patches `run`/`arun` (incl. streaming) on the Agent/Team/Workflow and installs class-level model (LLM) + tool (TOOL) hooks. Span tree:

```
AGENT / TEAM / WORKFLOW  (run / arun, incl. streaming)
  ↳ LLM   (model invocation)
  ↳ TOOL  (each tool call)
```

Combine with `@neatlogs.span` / `neatlogs.trace` / `neatlogs.log` for your own orchestration.

## Steps

1. **Install** → `references/1-install.md`
2. **Add init()** → `references/2-add-init.md`
3. **Set environment variables** → `references/3-set-env.md`
4. **Wrap the Agent with neatlogs.wrap()** → `references/4-wrap-agent.md`
5. **Add @span / trace / log to orchestration** → `references/5-spans-trace-log.md`
6. **Lifecycle (flush/shutdown)** → `references/6-flush-shutdown.md`

## Rules (apply to ALL steps)

- `neatlogs.init()` MUST run BEFORE importing `agno` (class-level model/tool hooks patch at import time). `load_dotenv()` runs before `init()`.
- Wrap each Agent/Team/Workflow you want traced: `agent = neatlogs.wrap(agent)`. Returns the same instance.
- `wrap()` creates the AGENT/LLM/TOOL spans — do NOT also wrap a single `agent.run()` in `@span`/`trace`. Use `@span` for YOUR orchestration only.
- Never hardcode API keys — use `os.getenv()`.
- For managed Neatlogs, omit `endpoint` and `NEATLOGS_ENDPOINT`; the SDK already uses `https://ingest.neatlogs.com`.
- `import neatlogs` at module top level.

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

- Show user-visible progress for install, edits, checks, restart, runtime verification, and platform confirmation; never print secrets.
- Run existing tests plus the project's build/package/type checks, restart the long-running process, and exercise the actual user-facing wrapped path.
- Inspect the full persisted span tree and returned semantic fields, not only a trace-list summary or local debug output. Confirm the nonce-qualified project trace is the fresh run, with one wrapper-owned hierarchy and no duplicate agent/LLM/tool spans. Offline/no-export verification alone is insufficient. Otherwise report the exact blocker and leave the result incomplete.

## Reference
- Combining wrap() with @span/trace/log → `references/5-spans-trace-log.md`
- Span kinds reference → `references/span-kinds.md`
- Sessions & end-users → `references/sessions-and-end-users.md`
