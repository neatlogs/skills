# Span kinds (Agno)

`neatlogs.wrap()` emits:
- **AGENT / TEAM / WORKFLOW** — `run` / `arun` (incl. streaming)
- **LLM** — model invocation (`agno.model.invoke`)
- **TOOL** — each tool/function call

Your own code: `@neatlogs.span(kind=...)`.
