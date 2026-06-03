---
name: neatlogs-ts-langchain
description: Use when adding neatlogs observability to a TypeScript/Node.js project that uses LangChain or LangGraph (depends on `@langchain/*` / `@langchain/langgraph`).
compatibility: Neatlogs Wizard Agent
metadata:
  author: neatlogs
  version: "2.0"
  language: typescript
  framework: langchain
---

# Neatlogs TypeScript Setup — LangChain / LangGraph

This project uses LangChain (`@langchain/*`) or LangGraph (`@langchain/langgraph`). The `langchain` instrumentation auto-traces LLM calls, chains, agents, tools, and retrievers. Your job is minimal: init before the LangChain import, and add ONE `span({ kind:'WORKFLOW' })` on the user-facing entry.

## Core mechanism

1. `await init({ instrumentations: ['langchain'] })` BEFORE importing `@langchain/*`.
2. Dynamic-`import()` the LangChain modules AFTER init.
3. `span({ kind:'WORKFLOW' }, fn)` on the entry that runs the chain/graph/agent. Everything inside is auto-traced.

## What the langchain instrumentation auto-traces (DO NOT manually wrap)

- `llm.invoke()` / `.stream()` → LLM spans
- chain / graph node execution → CHAIN spans
- LangChain tools → TOOL spans
- retrievers → RETRIEVER spans

## Steps

1. **Install** → `references/1-install.md`
2. **Add init() (before LangChain import)** → `references/2-add-init.md`
3. **Set environment variables** → `references/3-set-env.md`
4. **Add the WORKFLOW span (and only that)** → `references/4-add-workflow.md`
5. **Lifecycle (flush/shutdown)** → `references/5-lifecycle.md`

## Rules (apply to ALL steps)

- `await init(...)` MUST run BEFORE any `@langchain/*` import. Use dynamic `import()` AFTER init.
- `instrumentations: ['langchain']` covers LangChain AND LangGraph. The langchain instrumentor also captures the underlying LLM (no separate provider key needed for chat models routed through LangChain).
- The ONLY manual span you add is `span({ kind:'WORKFLOW' })` on the user-facing entry that runs the chain/graph/agent.
- NEVER wrap individual chains, graph nodes, LangChain tools, or `llm.invoke()` with `span()`/`trace()` — they are auto-traced; manual wrapping duplicates.
- All lifecycle calls are async. Never hardcode API keys — use `process.env`.

## Reference

- **Next.js setup (init via dynamic import in instrumentation.ts)** → `references/nextjs.md` — REQUIRED if the project is a Next.js app, else the server 500s with `Can't resolve 'crypto'` and emits no traces.
- Custom span()/trace() (rare here) → `references/decorators-and-traces.md`
- Prompt templates → `references/prompt-templates.md`
- Troubleshooting → `references/troubleshooting.md`
