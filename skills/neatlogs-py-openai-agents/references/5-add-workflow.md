# Step 5: Optional App-Owned WORKFLOW Span

## Add it only for real surrounding orchestration

The trace processor (Step 4) creates the canonical `WORKFLOW` root and traces agents, tools, handoffs, guardrails, and LLM calls. A standalone `Runner.run()` therefore renders without a manual decorator. Add at most one app-owned outer span:

```python
@neatlogs.span(kind="WORKFLOW", name="...")
```

on the **user-facing function that calls `Runner.run()`** (or `Runner.run_sync()` / `Runner.run_streamed()`) only when that function owns meaningful pre/post work or coordinates multiple runs. Do not add it around a pass-through that only calls one supported `Runner` entry point.

## How to Find It

Look for the function that:
- Is `main()`, a `@cli.command()`, a FastAPI route, or similar entry point, AND
- Calls `Runner.run(agent, ...)` / `await Runner.run(...)` / `Runner.run_sync(...)`

Only that outer function may get `@span(kind="WORKFLOW")`, and only when the preceding condition is true.

If the entry point is an async function run via `asyncio.run(...)`, decorate the async function that contains the `Runner.run()` call (not the `asyncio.run` line).

## WRONG vs RIGHT

```python
# ❌ WRONG — decorating an Agent definition / factory. Agents are auto-traced.
@neatlogs.span(kind="AGENT")          # REMOVE
def build_triage_agent() -> Agent:
    return Agent(name="Triage", instructions="...", tools=[...])

# ❌ WRONG — decorating a @function_tool. Tools are auto-traced.
@neatlogs.span(kind="TOOL")           # REMOVE
@function_tool
def lookup_order(order_id: str) -> str:
    ...

# ✅ RIGHT — the function that runs the agent IS the WORKFLOW.
@neatlogs.span(kind="WORKFLOW", name="run_support")
async def run_simulation() -> None:
    for query in SAMPLE_QUERIES:
        result = await Runner.run(triage_agent, query)
        print(result.final_output)
```

```python
# ✅ RIGHT — per-request entry (e.g. one query handler)
@neatlogs.span(kind="WORKFLOW", name="handle_query")
async def handle_query(query: str) -> str:
    result = await Runner.run(triage_agent, query)
    return result.final_output
```

## Do NOT Decorate Anything Else

- `Agent(...)` definitions / agent factories → auto-traced AGENT. Leave alone.
- `@function_tool` functions → auto-traced TOOL. Leave alone.
- Guardrail functions / `@input_guardrail` / `@output_guardrail` → auto-traced GUARDRAIL. Leave alone.
- `handoff(...)` calls → auto-traced. Leave alone.

These are declarative SDK constructs; the trace processor reads them. A manual decorator creates duplicate spans.

## Decorator Placement

```python
@cli.command()
@click.argument("query")
@neatlogs.span(kind="WORKFLOW", name="handle_query")
def ask(query: str):
    ...
```

## Verify BEFORE moving on

1. At most one app-owned `@span(kind="WORKFLOW")` for this path — on a real user-facing `Runner.run()` orchestrator; zero is correct for a single pass-through run.
2. NO Agent definition/factory, `@function_tool`, guardrail, or handoff has a neatlogs decorator.
3. The trace processor is registered once (Step 4): `add_trace_processor(neatlogs.openai_agents_processor())`. `init()` has NO `instrumentations=`.
