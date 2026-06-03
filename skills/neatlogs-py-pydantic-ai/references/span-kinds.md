# Span kinds reference (Pydantic AI)

`neatlogs.wrap(agent)` emits these automatically:
- **AGENT** — `agent.run` / `run_sync` / `run_stream` / `iter`
- **LLM** — `Model.request` / `request_stream` (one per model call); captures model, tokens, output
- **TOOL** — one per tool invocation; captures tool name, input, output

For YOUR own orchestration code, use `@neatlogs.span(kind=...)`:
- **WORKFLOW** — top-level entry orchestrating a whole job
- **CHAIN** — sequential processing steps
- **TOOL** — a custom tool/function NOT registered with the agent
- **RETRIEVER** — RAG retrieval
- **GUARDRAIL** — validation/filtering of output
