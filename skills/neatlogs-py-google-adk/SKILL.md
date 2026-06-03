---
name: neatlogs-py-google-adk
description: Use when adding neatlogs observability to a Python project that uses the Google Agent Development Kit (imports `google.adk`, builds an ADK agent/runner).
compatibility: Neatlogs Wizard Agent
metadata:
  author: neatlogs
  version: "1.0"
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
- Never hardcode API keys — use `os.getenv()`. ADK reads `GOOGLE_API_KEY` (set `GOOGLE_GENAI_USE_VERTEXAI=0` for AI-Studio keys).
- `import neatlogs` at module top level.

## Reference
- Combining wrap() with @span/trace/log → `references/5-spans-trace-log.md`
- Span kinds reference → `references/span-kinds.md`
