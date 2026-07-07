# Step 5: Add a WORKFLOW Span on Your Entry Point

## Why

`wrap(crew)` already opens a WORKFLOW span on `kickoff()` and nests AGENT/TOOL/LLM under it. Adding `@neatlogs.span(kind="WORKFLOW")` on YOUR user-facing function makes your orchestration code the trace root, so any pre/post work (loading inputs, writing outputs, multiple kickoffs) is grouped into the same trace as the crew run.

Add it on the **function a person/CLI/route invokes** that builds + kicks off the crew:

```python
@neatlogs.span(kind="WORKFLOW", name="...")
```

## How to Find It

Look for the function that:
- Is a `@cli.command()`, `main()`, FastAPI route, or similar entry point, AND
- Calls `crew.kickoff()` / `crew.kickoff_async()` (often after assembling `Crew(agents=..., tasks=...)` and wrapping it)

That entry point gets `@span(kind="WORKFLOW")`.

## WRONG vs RIGHT

```python
# ❌ WRONG — decorating an agent factory. Agents are traced by wrap().
@neatlogs.span(kind="AGENT")          # REMOVE
def create_researcher() -> Agent:
    return Agent(role="Researcher", goal="...", backstory="...")

# ❌ WRONG — decorating a @tool. Tools are auto-traced by wrap() (both dispatch paths).
@neatlogs.span(kind="TOOL")           # REMOVE
@tool
def web_search(query: str) -> str:
    ...

# ✅ RIGHT — the function that assembles, wraps, and kicks off the crew IS the WORKFLOW.
@neatlogs.span(kind="WORKFLOW", name="run_content_pipeline")
def run_content_pipeline(topic: str) -> str:
    researcher = create_researcher()
    writer = create_writer()
    crew = Crew(agents=[researcher, writer], tasks=[...], process=Process.sequential)
    crew = neatlogs.wrap(crew)
    return str(crew.kickoff())
```

```python
# ✅ RIGHT — if kickoff() is called directly in main(), decorate main() (or the
#            function it delegates to). Pick the single outermost entry point.
@neatlogs.span(kind="WORKFLOW", name="content_pipeline")
def main():
    crew = neatlogs.wrap(build_crew(topic))
    result = crew.kickoff()
    print(result)
```

## Do NOT Decorate Agents, Tasks, or Tools

- `create_*` agent factories → traced by wrap() as AGENT. Leave alone.
- `Task(...)` definitions / task factories → traced by wrap(). Leave alone.
- `@tool` functions → auto-traced by wrap() (via CrewStructuredTool.invoke) as TOOL. Leave alone.

## Decorator Placement

```python
@cli.command()
@click.option("--topic")
@neatlogs.span(kind="WORKFLOW", name="run_content_pipeline")
def run(topic: str):
    ...
```

## Verify BEFORE moving on

1. The user-facing `crew.kickoff()` caller has `@span(kind="WORKFLOW")`.
2. NO Agent factory, Task, or `@tool` function has an `@neatlogs.span()` decorator.
3. The crew was passed through `neatlogs.wrap(...)` (Step 4) before kickoff.
