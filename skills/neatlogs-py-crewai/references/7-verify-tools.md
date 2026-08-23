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

## Distinct unsupported/custom operations inside a tool

A tool may perform a distinct semantic operation that the CrewAI wrapper cannot
see. Add one child span for that operation only: `RETRIEVER` for custom search
or context lookup, and `EMBEDDING` for a custom/local embedder. The outer TOOL
span remains wrapper-owned; the child is not an upgrade or a duplicate tool
record.

```python
@tool("kb_search")
def kb_search_tool(query: str) -> str:
    """Search the product knowledge base."""
    with neatlogs.trace("kb_search", kind="RETRIEVER") as span:
        span.set_attribute("neatlogs.retriever.query", query)
        span.set_attribute("neatlogs.retriever.top_k", 3)
        results = KB.search(query, top_k=3)
        for i, result in enumerate(results):
            span.set_attribute(f"neatlogs.retriever.documents.{i}", json.dumps(result))
        span.set_attribute("neatlogs.retriever.output", json.dumps(results))
        return KB.format_results(results)
```

For a custom embedder, use `kind="EMBEDDING"` and the canonical
`neatlogs.embedding.model_name`, `neatlogs.embedding.text`,
`neatlogs.embedding.token_count`, and `neatlogs.embedding.output` attributes.
Do not add either child when another supported integration already captures the
same search or embedding call.

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

## Verification

- [ ] Plain action tools (`@tool` functions and `BaseTool` subclasses) are LEFT AS-IS — no `@neatlogs.span` decorator and no manual `trace()` inside (wrap() auto-traces them; a manual span would duplicate).
- [ ] A custom search inside a tool has one `RETRIEVER` child with indexed canonical document attributes; a custom embedder has one `EMBEDDING` child. Supported/captured operations have no extra manual span.
- [ ] NO Agent factory or Task has `@neatlogs.span()`.
- [ ] The crew was passed through `neatlogs.wrap(...)`; any `@neatlogs.span(kind="WORKFLOW")` is on your entry point (the `crew.kickoff()` caller).
