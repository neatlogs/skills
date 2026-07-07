# Step 7: Tools — What to Trace (and what NOT to)

`wrap(crew)` auto-traces tool calls. It installs class-level hooks on BOTH tool
dispatch paths CrewAI uses:
- `BaseTool.run` — `BaseTool` subclasses that define their own `_run` (e.g. a
  `class CalculatorTool(BaseTool)` with a `_run` method).
- `CrewStructuredTool.invoke` — the path `@tool`-decorated **function tools** go
  through (`ToolUsage._use` → `tool.invoke(...)`).

**This is version-independent.** Both paths are patched, so plain action tools
emit a `crewai.tool.<name>` TOOL span (with input/output) on every supported
crewai version — including old `0.130.x` and current `1.15.x`. You do NOT need a
version check, and you do NOT add a manual `trace()` to plain tools.

## Do NOT add `trace()`/`@neatlogs.span` to plain tools

Plain action tools (calculator, save_to_file, a web_search with no rich
attributes) are already traced by `wrap()`. Adding a manual span is wrong two ways:

```python
# ❌ WRONG — decorator. Loses attributes, conflicts with the framework.
@neatlogs.span(kind="TOOL", tool_name="web_search")   # REMOVE
@tool
def web_search(query: str) -> str:
    ...

# ❌ WRONG — manual trace() inside a PLAIN tool. wrap() already emits a TOOL span
# for this tool, so this produces a DUPLICATE span.
@tool("web_search")
def web_search(query: str) -> str:
    """Search the web."""
    with neatlogs.trace("web_search", kind="TOOL"):   # REMOVE — double span
        return _do_search(query)

# ✅ RIGHT — leave the tool as-is; wrap() traces it.
@tool("web_search")
def web_search(query: str) -> str:
    """Search the web."""
    return _do_search(query)
```

## The ONE case for a manual `trace()`: retrieval/embedding tools

Retrieval / embedding / vector-lookup tools should get a `with neatlogs.trace(kind="RETRIEVER")`
inside the body — NOT because the tool would otherwise be untraced (wrap() traces
it as a TOOL), but to upgrade it to a RETRIEVER span carrying the rich
`neatlogs.retrieval.*` attributes (query + documents) the dashboard renders.

```python
@tool("kb_search")
def kb_search_tool(query: str) -> str:
    """Search the product knowledge base."""
    with neatlogs.trace("kb_search", kind="RETRIEVER") as span:
        span.set_attribute("neatlogs.retrieval.query", query)
        span.set_attribute("neatlogs.retrieval.top_k", 3)
        results = KB.search(query, top_k=3)
        span.set_attribute("neatlogs.retrieval.documents", json.dumps(results))
        return KB.format_results(results)
```

This is the pattern from the official `neatlogs_support_bot` example. Do it for
retrieval tools on every crewai version.

## Agents and Tasks — never decorate (all versions)

```python
# ❌ WRONG
@neatlogs.span(kind="AGENT")          # REMOVE
def create_researcher() -> Agent:
    return Agent(role="Researcher", goal="...", backstory="...")

# ✅ RIGHT — no decorator; wrap(crew) traces agent/task execution
def create_researcher() -> Agent:
    return Agent(role="Researcher", goal="...", backstory="...")
```

`neatlogs.bind_templates(...)` and `neatlogs.register_crewai_task(...)` (Step 6) are fine — they attach prompt context, they are not spans.

## Verification

- [ ] Plain action tools (`@tool` functions and `BaseTool` subclasses) are LEFT AS-IS — no `@neatlogs.span` decorator and no manual `trace()` inside (wrap() auto-traces them; a manual span would duplicate).
- [ ] Retrieval/embedding tools have `with neatlogs.trace(kind="RETRIEVER")` + `neatlogs.retrieval.*` INSIDE the body (enrichment, not coverage).
- [ ] NO Agent factory or Task has `@neatlogs.span()`.
- [ ] The crew was passed through `neatlogs.wrap(...)`; any `@neatlogs.span(kind="WORKFLOW")` is on your entry point (the `crew.kickoff()` caller).
