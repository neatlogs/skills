---
name: neatlogs-ts-pi-agent
description: Use when adding neatlogs observability to a TypeScript/Node.js project that uses maintained `@earendil-works/pi-agent-core` / `@earendil-works/pi-ai` or legacy `@mariozechner` Pi packages, including `Agent`, `AgentHarness`, functional loops, and standalone stream functions.
metadata:
  author: neatlogs
  language: typescript
  framework: pi-agent
---

# Neatlogs TypeScript Setup — Pi Agent

This project uses **Pi Agent** (maintained as `@earendil-works/pi-agent-core`). Neatlogs instruments it with **`piAgentHooks()` from `neatlogs/pi-agent`**. The wrapper also supports legacy `@mariozechner` releases through the same event interface.

## Core mechanism — `piAgentHooks(agent)`

`Agent` exposes `subscribe(listener)` and emits lifecycle events (`agent_*`, `turn_*`, `message_*`, `tool_execution_*`). Neatlogs translates them into spans. For maintained `AgentHarness`, it additionally wraps model-producing `compact()` and summarizing `navigateTree()` operations because those calls occur outside the Agent event loop. There is no import-order rule.

One `agent.prompt()` = **one trace**:

```
AGENT  pi_agent.run                  (agent_start → agent_end)
 ├─ CHAIN pi_agent.turn.1            (turn_start → turn_end)
 │   ├─ LLM  pi_agent.llm.<model>    (message_start → message_end = real provider latency)
 │   └─ TOOL pi_agent.tool.<name>    (tool_execution_start → tool_execution_end)
 └─ CHAIN pi_agent.turn.2            (the post-tool-result turn)
     └─ LLM  pi_agent.llm.<model>
```

| Span | Carries |
|------|---------|
| **AGENT** | run input (first user message), final output, `neatlogs.agent.stop_reason` + `neatlogs.error.message` on an aborted/errored run |
| **CHAIN** | `neatlogs.chain.turn_index`, the message that prompted the turn, the turn's assistant text (or the tool calls it made), `neatlogs.chain.tool_result_count` |
| **LLM** | model / `response_model` / provider / api, input messages, output + `tool_calls.*`, token counts (incl. cache read/write), **exact `cost_usd` from pi-ai's own pricing**, `metrics.ttft_ms`, `is_streaming`, `stop_reason` |
| **TOOL** | tool name, `call_id`, input args, result, `is_error`, `is_streaming` for tools that emit partial updates |

## Steps

1. [Install and check the Pi version](references/1-install.md)
2. [Add `init()` and `piAgentHooks()`](references/2-init-and-wrap.md)
3. [Set environment variables](references/3-set-env.md)
4. [Verify every Agent or harness](references/4-verify.md)
5. [Handle lifecycle and flushing](references/5-lifecycle.md)

## Rules (apply to ALL steps)

- `piAgentHooks` patches the **instance** you pass (it subscribes to it), NOT the module — so **plain static imports are fine**. There is no "init before import" rule for Pi Agent, unlike provider-SDK wrappers.
- USE the wrapped reference. `piAgentHooks` subscribes in place AND returns the agent, so `const agent = piAgentHooks(new Agent({...}))` then call `agent.prompt(...)`.
- Call it on **every** `Agent` instance you want traced. Wrapping is **idempotent** — calling it twice on the same instance is a no-op, so it never double-traces.
- NEVER pass `instrumentations: [...]`. `piAgentHooks` is the sole capture point for Pi-routed model calls; `init()` rejects provider keys.
- Pi calls the model through its `pi-ai` package, not a bare provider SDK, so do **not** also wrap the provider (`wrapOpenAI`, `wrapAnthropic`, …) for Pi-routed calls. Only wrap a provider client the app calls **directly** outside Pi.
- Cost is **not** re-derived from tokens: pi-ai prices each call against its own model registry and neatlogs carries that exact figure through as `neatlogs.llm.cost_usd`.
- Do NOT manually wrap `agent.prompt()` in `span()`/`trace()` on top of `piAgentHooks` — that double-traces. Nesting a wrapped agent INSIDE your own `span()` is fine and correct: the AGENT span parents to it.
- All lifecycle calls are async: `await init()`, `await flush()`, `await shutdown()`.
- Never hardcode API keys — use `process.env`.
- For managed Neatlogs, omit `endpoint`, `baseUrl`, and `NEATLOGS_ENDPOINT`; the SDK already uses `https://ingest.neatlogs.com`.

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

- Print concise user-visible progress before and after install, code changes, build, restart, runtime verification, and platform confirmation. Never print secrets.
- Run the project's existing build/typecheck/test commands with its detected package manager. Source inspection alone is not verification.
- For servers and startup hooks, build and start a fresh process after instrumentation changes, then exercise the actual instrumented route/action/entry point.
- Run a safe bounded verification through the real instrumented entry point. Inspect the full persisted span tree and returned semantic fields, not only a trace-list summary or local debug output. Confirm the nonce-qualified project trace is the fresh run, with one canonical span per operation and no duplicate LLM/tool/agent spans. An offline/no-export verifier is insufficient by itself.
- Do not claim completion until all applicable checks pass. If runtime or ingestion cannot be confirmed, report the exact blocker and leave the result incomplete.

## Reference

- [Low-level functional API](references/low-level-api.md) — required for functional loops and standalone stream functions.
- [Full span coverage matrix](references/span-coverage.md) — Agent, AgentHarness, streaming, tools, abort, and state-only methods.
- [Sessions and end-users](references/sessions-and-end-users.md)
- [Custom spans for non-Pi code](references/decorators-and-traces.md)
