# Step 5: Add the WORKFLOW Span (and ONLY that)

## The One Decorator You Add

The trace processor (Step 4) traces agents, tools, handoffs, guardrails, and LLM calls. The one thing it cannot do is create the trace root. Add exactly one:

```python
@neatlogs.span(kind="WORKFLOW", name="...")
```

on the **user-facing function that calls `Runner.run()`** (or `Runner.run_sync()` / `Runner.run_streamed()`) — the function a person/CLI/route actually invokes.

Without this WORKFLOW root, every traced agent/tool/handoff/LLM span becomes an orphan in its own trace and nothing shows up grouped together.

## How to Find It

Look for the function that:
- Is `main()`, a `@cli.command()`, a FastAPI route, or similar entry point, AND
- Calls `Runner.run(agent, ...)` / `await Runner.run(...)` / `Runner.run_sync(...)`

That function — and ONLY that function — gets `@span(kind="WORKFLOW")`.

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

1. EXACTLY ONE `@span(kind="WORKFLOW")` in the project — on the `Runner.run()` caller.
2. NO Agent definition/factory, `@function_tool`, guardrail, or handoff has a neatlogs decorator.
3. The trace processor is registered once (Step 4): `add_trace_processor(neatlogs.openai_agents_processor())`. `init()` has NO `instrumentations=`.
