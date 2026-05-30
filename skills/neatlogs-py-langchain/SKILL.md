---
name: neatlogs-py-langchain
description: >
  Instrument a Python project that uses LangChain or LangGraph with the "langchain" auto-instrumentor.
compatibility: Neatlogs Wizard Agent
metadata:
  author: neatlogs
  version: "2.0"
  language: python
  framework: langchain
---

# Neatlogs Python Setup — LangChain / LangGraph

This project uses LangChain or LangGraph. The `"langchain"` auto-instrumentor handles most tracing automatically. Your job is minimal: add ONE `@span(kind="WORKFLOW")` on the user-facing entry point, and add `neatlogs.trace()` + prompt templates inside node functions that call the LLM.

## What the "langchain" instrumentor auto-traces (DO NOT manually decorate)

- ALL `@tool`-decorated functions → TOOL span
- ALL LangGraph node executions → spans
- ALL `llm.invoke()` / `llm.ainvoke()` calls → LLM span
- ALL `chain.invoke()` / `chain.ainvoke()` calls → CHAIN span
- ALL `retriever.get_relevant_documents()` calls → RETRIEVER span
- ToolNode tool dispatch → TOOL span

## What the underlying provider instrumentor auto-traces

The `langchain` instrumentor does NOT capture embeddings — LangChain has no embedding callback. Embeddings are captured by the underlying **provider** instrumentor (`openai`, `cohere`, etc.), which the wizard adds automatically when it detects `langchain-openai`/`langchain-cohere`/etc. That instrumentor patches the provider SDK below the LangChain layer, so:

- `OpenAIEmbeddings`, `CohereEmbeddings`, etc. → captured as EMBEDDING spans automatically. DO NOT manually decorate them.

## What you MUST do manually

1. Add `@neatlogs.span(kind="WORKFLOW")` on the user-facing function that calls `graph.invoke()` / `graph.ainvoke()`
2. Add `with neatlogs.trace(kind="LLM", ...)` + `SystemPromptTemplate` / `UserPromptTemplate` inside node functions around LLM calls — this captures prompt template structure for the dashboard
3. ONLY for CUSTOM embedding functions (a hand-rolled embedder, local model, or raw HTTP call that no provider instrumentor covers): add `@neatlogs.span(kind="EMBEDDING")` + attributes — see `references/6.5-embeddings.md`

## Steps

1. **Install SDK** → `references/1-install-sdk.md`
2. **Add init()** → `references/2-add-init.md`
3. **Set environment variables** → `references/3-set-env.md`
4. **Add WORKFLOW span** → `references/4-add-workflow.md`
5. **Wrap LLM calls with trace() + templates** → `references/5-wrap-llm-calls.md`
6. **Verify tool functions are untouched** → `references/6-verify-tools.md`
6.5. **Embeddings: decorate ONLY custom ones** → `references/6.5-embeddings.md`
7. **Add flush/shutdown** → `references/7-flush-shutdown.md`

## Rules (apply to ALL steps)

- `neatlogs.init()` MUST execute BEFORE any LLM library imports.
- If `load_dotenv()` exists, it MUST run BEFORE `neatlogs.init()`.
- Never hardcode API keys in source. Use `os.getenv()`.
- Add imports ONLY for what a file actually uses:
  - File calls `neatlogs.span(...)` or `neatlogs.trace(...)` → add `import neatlogs`.
  - File only defines `SystemPromptTemplate`/`UserPromptTemplate` objects → add ONLY `from neatlogs import SystemPromptTemplate, UserPromptTemplate`. Do NOT add a bare `import neatlogs` — it would be an unused import.
- When present, `import neatlogs` goes at module top level, never inside functions.
- `@neatlogs.span()` goes BELOW framework decorators (`@retry`, `@app.route`) — closest to `def`.
- Minimal edits only. Add decorators + imports. Do not reformat, add comments, or refactor.
- NEVER add `@neatlogs.span()` to functions that have `@tool` from `langchain_core.tools`.
- NEVER add `@neatlogs.span()` to LangGraph node functions (the instrumentor traces them).
- NEVER manually decorate framework embedding classes (`OpenAIEmbeddings` etc.) — the provider instrumentor traces them.
- The ONLY `@span(kind="WORKFLOW")` you add is on the graph.invoke() caller. `@span(kind="EMBEDDING")` is added ONLY for custom embedders (step 6.5).

## Reference

- Span kinds → `references/span-kinds.md`
