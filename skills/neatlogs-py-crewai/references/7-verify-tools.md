# Step 7: Tools — Version Check + What to Trace

`wrap(crew)` patches `BaseTool.run`, which covers tools dispatched through it. But on newer `crewai` some native tool calls bypass `BaseTool.run`, so tool coverage still depends on the installed `crewai` version. Do the version check FIRST, then apply the matching rule.

## 0. Check the CrewAI version

```bash
python -c "import crewai; print(crewai.__version__)"
```

| Installed `crewai` | TOOL spans from wrap() reliable? |
|---|---|
| `>=1.9.3, <1.14` | YES — tool calls go through `BaseTool.run`, which `wrap()` patches → TOOL spans emitted. (This is the range the official examples pin.) |
| `>=1.14` | NOT ALWAYS — some native tool calls bypass `BaseTool.run` (`ToolUsage._use` / `_handle_native_tool_calls`), so those TOOL spans can be lost. |

> If the project allows it, prefer pinning `crewai>=1.9.3,<1.14` (matches neatlogs' own examples). On `>=1.14` add manual `trace()` inside the tool bodies you need visible.

## NEVER use the `@neatlogs.span` decorator on tools

Regardless of version, do NOT stack `@neatlogs.span(kind="TOOL")` above/below `@tool`. A decorator can't carry the rich `neatlogs.retrieval.*` / `neatlogs.tool.*` attributes and conflicts with the framework. When you need a tool span, use `with neatlogs.trace(...)` INSIDE the function body (below).

```python
# ❌ WRONG — decorator. Loses attributes, conflicts with wrap()'s BaseTool.run hook.
@neatlogs.span(kind="TOOL", tool_name="web_search")   # REMOVE
@tool
def web_search(query: str) -> str:
    ...
```

## What to do, by tool type

### A. Plain action tools (calculator, save_to_file, web_search with no rich attrs)
- crewai `<1.14`: leave undecorated — traced via `BaseTool.run`.
- crewai `>=1.14`: add a `trace()` inside the body so the span isn't lost:
  ```python
  @tool("web_search")
  def web_search(query: str) -> str:
      """Search the web."""
      with neatlogs.trace("web_search", kind="TOOL") as span:
          span.set_attribute("neatlogs.tool.name", "web_search")
          span.set_attribute("neatlogs.tool.input", query)
          result = _do_search(query)
          span.set_attribute("neatlogs.tool.output", str(result)[:2000])
          return result
  ```

### B. Retrieval / embedding / external-IO tools (KB search, vector lookup) — ANY version
Wrap the body with `kind="RETRIEVER"` and set `neatlogs.retrieval.*` so the dashboard shows query + documents. This is the pattern from the official `neatlogs_support_bot` example:

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

Do this for retrieval tools on EVERY crewai version — even where auto-tracing works, the auto TOOL span lacks the `neatlogs.retrieval.*` attributes.

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

- [ ] Ran the crewai version check and applied the matching rule.
- [ ] NO `@tool` function has a `@neatlogs.span(...)` DECORATOR.
- [ ] Retrieval/embedding tools have `with neatlogs.trace(kind="RETRIEVER")` + `neatlogs.retrieval.*` INSIDE the body.
- [ ] On crewai `>=1.14`, tools you need visible have a `trace()` inside the body (native calls that bypass `BaseTool.run` won't emit them).
- [ ] NO Agent factory or Task has `@neatlogs.span()`.
- [ ] The crew was passed through `neatlogs.wrap(...)`; any `@neatlogs.span(kind="WORKFLOW")` is on your entry point (the `crew.kickoff()` caller).
