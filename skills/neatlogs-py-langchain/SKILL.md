---
name: neatlogs-py-langchain
description: Use when adding neatlogs observability to a Python project that uses LangChain or LangGraph (imports `langchain*` / `langgraph`, builds chains, runnables, or a graph).
metadata:
  author: neatlogs
  language: python
  framework: langchain
---

# Neatlogs Python Setup — LangChain / LangGraph

This project uses LangChain or LangGraph. Neatlogs offers **two ways** to instrument it:

1. **`neatlogs.langchain_handler()`** — a LangChain callback handler you attach per call via `config={"callbacks": [handler]}`. This is the **recommended, first-class** path (LangChain's own callback system; explicit control over exactly which calls are traced). This skill uses it throughout.
2. **`instrumentations=["langchain"]`** on `init()` — zero-touch auto-instrumentation (OpenInference) that traces LangChain/LangGraph globally without editing call sites. Use this when you can't (or don't want to) thread a handler through your code.

Pick ONE — don't combine them (that double-traces). The rest of this skill shows the handler approach.

## Core mechanism — `neatlogs.langchain_handler()`

Create ONE handler and pass it via `config={"callbacks": [handler]}` on the calls you want traced. The handler emits the span tree from LangChain's callback events:

```
CHAIN  chain / graph execution
  ↳ LLM        chat-model / llm call
  ↳ TOOL       @tool invocation (via ToolNode)
  ↳ RETRIEVER  retriever call
```

```python
import neatlogs
from langchain_openai import ChatOpenAI

handler = neatlogs.langchain_handler()
model = ChatOpenAI(model="gpt-4o")
result = model.invoke("Hello", config={"callbacks": [handler]})
```

### LangGraph: attach at the GRAPH invocation — NOT the per-node model call

For LangGraph, attach the handler at the **graph invocation** (`app.invoke(...)` / `ainvoke` / `stream` / `astream`), not on the per-node `llm.invoke()`. LangGraph fires the per-node `on_chain_start` only on the **graph-level callback manager**, so a handler passed to a single node's model call never sees the node boundaries — you get no node spans and the LLM span orphans to the workflow root (flat, no node hierarchy). Attach once at the graph invocation and each node gets its own span with the LLM nested under it. Do not add manual spans inside nodes.

```python
def analyst_node(state):
    response = llm.invoke(messages)                                    # no per-node handler
    return {"messages": [response]}

# ✅ attach at the graph invocation — nodes + nested LLMs all get spans
app.invoke(state, config={"callbacks": [handler]})                     # graph level ✅
# NOT: llm.invoke(messages, config={"callbacks": [handler]})           # per-node ❌ (no node spans, LLM orphans)
```

The same boundary rule applies asynchronously. An `async def` node should await
`llm.ainvoke(...)` without a per-node callback; attach the handler once to
`await app.ainvoke(..., config={"callbacks": [handler]})` or
`app.astream(..., config={"callbacks": [handler]})`. Do not call synchronous
`invoke()` from an async node, and do not `await app.astream(...)` itself—iterate
it with `async for`.

(Plain LangChain — LCEL chains / bare `model.invoke()` — is the opposite: attach per model/chain call as in the example above. The graph-level rule is LangGraph-specific.)

### Deep Agents (`deepagents`) — prebuilt harness, attach on the top-level invoke

Deep Agents (`from deepagents import create_deep_agent`) is a LangGraph harness — you do NOT write the nodes, so there's no per-node model call to attach to. Pass the handler on the agent's top-level `invoke` / `ainvoke` / `stream`:

```python
handler = neatlogs.langchain_handler()
agent = create_deep_agent(model="openai:gpt-4o-mini", tools=[...], system_prompt="...")
result = agent.invoke(
    {"messages": [{"role": "user", "content": "..."}]},
    config={"callbacks": [handler]},
)
```

For hand-written LangGraph (your own nodes) as well as prebuilt harnesses (Deep Agents), the top-level / graph invocation is the attach point — use it. (Consistent with the graph-level rule above.)

Use a WORKFLOW span and `neatlogs.log` only for your own surrounding orchestration; the handler-owned spans nest underneath. Never add manual LLM, node, chain, tool, or retriever spans for operations the handler captures.

## What the handler captures (DO NOT manually decorate)

- Chat-model / LLM calls → LLM span (model, tokens, latency)
- `@tool` invocations via ToolNode → TOOL span
- Retriever calls → RETRIEVER span
- Chain / node execution → CHAIN span

Token usage is read from both LangChain's standard `usage_metadata` and provider `llm_output.token_usage`, normalized to `neatlogs.llm.token_count.*` across providers — including Gemini (`prompt_token_count` / `candidates_token_count`), cache tokens, and reasoning tokens. Async callbacks (`ainvoke` / `astream`) are supported, and LangGraph node spans use the bare node name (e.g. `researcher`). Nothing to configure.

## Steps

1. **Install SDK** → `references/1-install-sdk.md`
2. **Add init()** → `references/2-add-init.md`
3. **Set environment variables** → `references/3-set-env.md`
4. **Create + attach the callback handler** → `references/4-attach-handler.md`
5. **Optionally add an app-owned WORKFLOW for real surrounding orchestration** → `references/5-add-workflow.md`
6. **Verify handler-owned LLM calls are not manually wrapped** → `references/6-wrap-llm-calls.md`
7. **Verify tool functions are untouched** → `references/7-verify-tools.md`
7.5. **Embeddings: decorate ONLY custom ones** → `references/7.5-embeddings.md`
8. **Add flush/shutdown** → `references/8-flush-shutdown.md`

## Rules (apply to ALL steps)

- `neatlogs.init()` MUST execute BEFORE any LangChain library imports.
- If `load_dotenv()` exists, it MUST run BEFORE `neatlogs.init()`.
- This skill uses the **callback handler**; if you go that route, do NOT ALSO pass `instrumentations=["langchain"]` to `init()` — running both double-traces. (`instrumentations=["langchain"]` is a valid standalone alternative — see the intro — just don't combine the two. Provider instrumentors for embeddings are a separate concern — see step 7.5.)
- Create ONE `neatlogs.langchain_handler()` and pass it via `config={"callbacks": [handler]}`. For plain LangChain (LCEL chains / bare model calls) attach per model/chain call. For LangGraph attach at the graph invocation (`app.invoke(..., config={"callbacks": [handler]})`), NOT the per-node `llm.invoke()`.
- Never hardcode API keys in source. Use `os.getenv()`.
- For managed Neatlogs, omit `endpoint` and `NEATLOGS_ENDPOINT`; the SDK already uses `https://ingest.neatlogs.com`.
- Add imports ONLY for what a file actually uses:
  - File calls `neatlogs.langchain_handler(...)` / `neatlogs.span(...)` / `neatlogs.log(...)` → add `import neatlogs`.
- When present, `import neatlogs` goes at module top level, never inside functions.
- `@neatlogs.span()` goes BELOW framework decorators, closest to `def`.
- Minimal edits only. Add the handler + decorators + imports. Do not reformat or refactor.
- NEVER add `@neatlogs.span()` to `@tool` functions or LangGraph node functions.
- The handler self-roots a parentless supported call. Add at most one app-owned `@span(kind="WORKFLOW")` on a user-facing entry only when it performs meaningful pre/post work or coordinates multiple calls. `@span(kind="EMBEDDING")` is added only for a custom embedder (step 7.5).
- NEVER put `neatlogs.trace(kind="LLM")`, `@neatlogs.span`, or another provider instrumentor around `invoke`/`stream`, graph nodes, tools, or retrievers captured by the handler.

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

- Print concise user-visible progress before and after install, edits, dependency/import checks, restart, runtime verification, and platform confirmation. Never print secrets.
- Run existing tests plus the project's build/package/type checks after editing. Restart the long-running process so initialization and handler wiring are loaded.
- Exercise the actual user-facing chain/graph path. Inspect the full persisted span tree and returned semantic fields, not only a trace-list summary or local debug output. Confirm the nonce-qualified project trace is the fresh run, with one handler-owned hierarchy and no duplicate LLM/chain/node/tool spans. An offline/no-export verifier is insufficient by itself.
- Do not claim completion until all applicable checks pass. If runtime or ingestion cannot be confirmed, report the exact blocker and leave the result incomplete.

## Reference

- Span kinds → `references/span-kinds.md`
- Sessions & end-users (per-turn `identify()` for customer analytics) → `references/sessions-and-end-users.md`
