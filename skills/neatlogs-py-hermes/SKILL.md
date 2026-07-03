---
name: neatlogs-py-hermes
description: Use when adding neatlogs observability to a Python project that uses the Hermes agent (NousResearch/hermes-agent) as a LIBRARY — i.e. it imports `run_agent` / constructs `AIAgent(...)` in its own code.
compatibility: Neatlogs Wizard Agent
metadata:
  author: neatlogs
  version: "1.0"
  language: python
  framework: hermes
---

# Neatlogs Python Setup — Hermes (library mode)

This project uses **Hermes** (`from run_agent import AIAgent`) as a library in its
own Python code. Neatlogs instruments it with the **`hermes` instrumentation**
(plus `openai`), enabled in `neatlogs.init(...)`.

> **Are they running the standalone `hermes` CLI instead of writing Python?**
> Then this skill does NOT apply — there's no source to add `init()` to. Use the
> **observer plugin** instead: `pip install neatlogs` and `hermes plugins enable
> neatlogs` (it traces the CLI/gateway with zero code). This skill is only for
> code that imports `run_agent`/`AIAgent`.

## Core mechanism — `neatlogs.init(instrumentations=["hermes"])`

The `hermes` instrumentor patches `AIAgent.run_conversation` (an **AGENT** span)
and `ToolRegistry.dispatch` (a **TOOL** span per tool call). Hermes' LLM calls go
through the `openai` SDK (pointed at OpenRouter) — and `"hermes"` **auto-loads
`openai`** for the **LLM** spans, so you only list `"hermes"`. Span tree:

```
AGENT  hermes.run_conversation   (one agentic run)
  ↳ LLM   chat.completions.create  (via openai → OpenRouter)
  ↳ TOOL  hermes.tool.<name>       (each tool dispatch)
```

`wrap()` is an optional equivalent (`agent = neatlogs.wrap(AIAgent(...))`) — it's
the same class-level patch, so prefer the `instrumentations=[...]` form.

## Steps

1. **Install** → `references/1-install.md`
2. **Add init() BEFORE importing run_agent** → `references/2-add-init.md`
3. **Set environment variables** → `references/3-set-env.md`
4. **Run the agent (no per-call changes needed)** → `references/4-run-agent.md`
5. **Add @span / trace / log to your orchestration** → `references/5-spans-trace-log.md`
6. **Lifecycle (flush/shutdown)** → `references/6-flush-shutdown.md`

## Rules (apply to ALL steps)

- `neatlogs.init(instrumentations=["hermes"])` MUST run BEFORE
  `from run_agent import AIAgent` — the instrumentor patches the class at import
  time, so a later init misses it. `load_dotenv()` runs before `init()`.
  (`"hermes"` auto-loads `openai` for the LLM spans — no need to add it yourself.)
- Hermes isn't on PyPI — it's git-installed (see step 1).
- Hermes routes LLM calls through OpenRouter by default; if you use a non-OpenAI
  provider adapter (anthropic / bedrock / gemini), add that provider to the
  instrumentations list too (e.g. `["hermes", "anthropic"]`).
- Never hardcode API keys — use `os.getenv()`.
- `import neatlogs` at module top level.

## Reference
- Combining the instrumentation with @span/trace/log → `references/5-spans-trace-log.md`
- Sessions & end-users (group a conversation's runs, attribute to a customer) → `references/sessions-and-end-users.md`
- Span kinds reference → `references/span-kinds.md`
