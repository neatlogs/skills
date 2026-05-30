# Step 4: Add the WORKFLOW Span (and ONLY that)

## The One Decorator You Add

In a CrewAI project the instrumentor auto-traces the crew, agents, tasks, and tools. The one thing it cannot do is create the trace root. Add exactly one:

```python
@neatlogs.span(kind="WORKFLOW", name="...")
```

on the **user-facing function that calls `crew.kickoff()`** — the function a person/CLI/route invokes, which builds the crew and runs it.

Without this WORKFLOW root, every auto-traced agent/task/tool/LLM span becomes an orphan in its own trace and nothing shows up grouped together.

## How to Find It

Look for the function that:
- Is a `@cli.command()`, `main()`, FastAPI route, or similar entry point, AND
- Calls `crew.kickoff()` / `crew.kickoff_async()` (often after assembling `Crew(agents=..., tasks=...)`)

That function — and ONLY that function — gets `@span(kind="WORKFLOW")`.

## WRONG vs RIGHT

```python
# ❌ WRONG — decorating an agent factory. Agents are auto-traced.
@neatlogs.span(kind="AGENT")          # REMOVE
def create_researcher() -> Agent:
    return Agent(role="Researcher", goal="...", backstory="...")

# ❌ WRONG — decorating a @tool. Tools are auto-traced.
@neatlogs.span(kind="TOOL")           # REMOVE
@tool
def web_search(query: str) -> str:
    ...

# ✅ RIGHT — the function that assembles and kicks off the crew IS the WORKFLOW.
@neatlogs.span(kind="WORKFLOW", name="run_content_pipeline")
def run_content_pipeline(topic: str) -> str:
    researcher = create_researcher()
    writer = create_writer()
    crew = Crew(agents=[researcher, writer], tasks=[...], process=Process.sequential)
    return str(crew.kickoff())
```

```python
# ✅ RIGHT — if kickoff() is called directly in main(), decorate main() (or the
#            function it delegates to). Pick the single outermost entry point.
@neatlogs.span(kind="WORKFLOW", name="content_pipeline")
def main():
    crew = build_crew(topic)
    result = crew.kickoff()
    print(result)
```

## Do NOT Decorate Agents, Tasks, or Tools

- `create_*` agent factories → auto-traced as AGENT. Leave alone.
- `Task(...)` definitions / task factories → auto-traced. Leave alone.
- `@tool` functions → auto-traced as TOOL. Leave alone.

## Decorator Placement

```python
@cli.command()
@click.option("--topic")
@neatlogs.span(kind="WORKFLOW", name="run_content_pipeline")
def run(topic: str):
    ...
```

## Verify BEFORE moving on

1. EXACTLY ONE `@span(kind="WORKFLOW")` in the project — on the `crew.kickoff()` caller.
2. NO Agent factory, Task, or `@tool` function has an `@neatlogs.span()` decorator.
3. `instrumentations=["crewai", "<provider>"]` matches the LLM backend (Step 2).
