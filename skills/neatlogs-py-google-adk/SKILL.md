---
name: neatlogs-py-google-adk
description: Use when adding neatlogs observability to a Python project that uses the Google Agent Development Kit (imports `google.adk`, builds an ADK agent/runner).
metadata:
  author: neatlogs
  language: python
  framework: google-adk
---

# Neatlogs Python Setup — Google ADK

This project uses the **Google ADK** (`google.adk.runners.Runner` / `InMemoryRunner`, `LlmAgent`). Neatlogs instruments it with **`neatlogs.wrap(runner)`**.

## Core mechanism — `neatlogs.wrap(runner)`

`neatlogs.wrap()` patches the Runner's `run()` (sync generator) and `run_async()` (async generator), tracing each invocation as a WORKFLOW span with token usage, output, and tool-call metadata extracted from the event stream.

```
WORKFLOW  google_adk.runner.run_async   (per invocation)
```

Combine with `@neatlogs.span` / `neatlogs.trace` / `neatlogs.log` for your own orchestration; the runner span nests under them.

## Steps

1. **Install** → `references/1-install.md`
2. **Add init()** → `references/2-add-init.md`
3. **Set environment variables** → `references/3-set-env.md`
4. **Wrap the Runner with neatlogs.wrap()** → `references/4-wrap-runner.md`
5. **Add @span / trace / log to orchestration** → `references/5-spans-trace-log.md`
6. **Lifecycle (flush/shutdown)** → `references/6-flush-shutdown.md`

## Rules (apply to ALL steps)

- `neatlogs.init()` MUST run BEFORE importing `google.adk`. `load_dotenv()` runs before `init()`.
- Wrap the Runner instance: `runner = neatlogs.wrap(InMemoryRunner(agent=..., app_name=...))`. Returns the same instance; `run_async()` stays an async generator (consume with `async for`).
- Do NOT wrap a single `runner.run_async()` loop in `@span`/`trace` — `wrap()` already opens the WORKFLOW span. Use `@span` for YOUR orchestration only.
- The wrapped runner is the capture owner for the ADK run and its model/tool metadata. Do NOT add manual LLM/tool decorators or a second provider/framework instrumentor inside that run.
- Never hardcode API keys — use `os.getenv()`. ADK reads `GOOGLE_API_KEY` (set `GOOGLE_GENAI_USE_VERTEXAI=0` for AI-Studio keys).
- For managed Neatlogs, omit `endpoint` and `NEATLOGS_ENDPOINT`; the SDK already uses `https://ingest.neatlogs.com`.
- `import neatlogs` at module top level.

## Live completion gate (wizard or standalone coding agent)

This skill does not grant platform access. Immediately before exercising the real path, record the current UTC timestamp. After the run, call the already-connected Neatlogs platform MCP's existing `get_trace_context(created_after=<UTC timestamp>)` directly to select the latest trace in the intended project; do not make preliminary MCP discovery calls. While its `status` is `processing` or `finalization_status` is `pending`, poll that same trace with `get_trace_context(trace_id=<trace_id>)`. Once finalized, page with `get_trace_context(trace_id=<trace_id>, offset=<next_offset>)` until `next_offset` is null, and verify that all `span_count` spans were inspected. If MCP is unavailable, ask the user to configure `https://ingest.neatlogs.com/mcp` with the project key stored as a client secret; never print or request the key in chat, and leave verification incomplete.

- Show user-visible progress for install, edits, checks, restart, runtime verification, and platform confirmation; never print secrets.
- Run existing tests plus the project's build/package/type checks, restart the long-running process, and exercise the actual user-facing wrapped runner path.
- Inspect the full persisted span tree and attributes, not only a trace-list summary or local debug output. Confirm the latest project trace is the fresh run, with one runner-owned hierarchy and no duplicate workflow/LLM/tool spans. Offline/no-export verification alone is insufficient. Otherwise report the exact blocker and leave the result incomplete.

## Reference
- Combining wrap() with @span/trace/log → `references/5-spans-trace-log.md`
- Span kinds reference → `references/span-kinds.md`
- Sessions & end-users (group turns, per-user analytics via `identify()`) → `references/sessions-and-end-users.md`
