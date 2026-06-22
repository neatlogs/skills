# Span kinds (Hermes — library mode)

`init(instrumentations=["hermes", "openai"])` emits:
- **AGENT** — `hermes.run_conversation` (one agentic run; the trace root)
- **LLM** — `chat.completions.create` (via the `openai` instrumentor → OpenRouter)
- **TOOL** — `hermes.tool.<name>` (each `ToolRegistry.dispatch`)

Your own code: `@neatlogs.span(kind=...)`.

Note: the standalone `hermes` CLI/gateway (observer plugin, not this skill) also
emits GUARDRAIL (dangerous-command approvals), nested AGENT (subagents), and TASK
(kanban) spans. Library mode via `run_conversation()` covers AGENT/LLM/TOOL.
