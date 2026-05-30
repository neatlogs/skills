# Step 6: Verify Agents, Tools, Handoffs, and Guardrails Are Untouched

## Action

Confirm that NO Agent definition, `@function_tool`, guardrail, or handoff has a neatlogs decorator. This is a verification pass, not an action step.

## Why

The `"openai_agents"` instrumentor automatically traces every construct of the OpenAI Agents SDK:
- `Runner.run()` and each `Agent` turn → AGENT spans (with the agent's `instructions` as the prompt)
- `@function_tool` functions → TOOL spans
- Handoffs → spans
- Input/output guardrails → GUARDRAIL spans
- LLM calls → LLM spans

Adding `@neatlogs.span()` / `@neatlogs.trace()` to any of them creates duplicate spans.

## What to Check

Grep the project for `@function_tool`, `Agent(`, `handoff(`, `@input_guardrail`, `@output_guardrail`, and guardrail function definitions. For each, verify there is NO `@neatlogs.span(...)` and NO `with neatlogs.trace(...)`.

## If You Find a Violation — Remove It

```python
# ❌ FOUND — remove the decorator
@neatlogs.span(kind="TOOL", tool_name="lookup_order")   # REMOVE
@function_tool
def lookup_order(order_id: str) -> str:
    """Look up an order by ID."""
    ...

# ✅ SHOULD BE — just @function_tool
@function_tool
def lookup_order(order_id: str) -> str:
    """Look up an order by ID."""
    ...
```

```python
# ❌ FOUND — remove the decorator on the agent
@neatlogs.span(kind="AGENT")          # REMOVE
def make_billing_agent() -> Agent:
    return Agent(name="Billing", instructions="...", tools=[...])

# ✅ SHOULD BE — no decorator
def make_billing_agent() -> Agent:
    return Agent(name="Billing", instructions="...", tools=[...])
```

```python
# ❌ FOUND — remove from a guardrail function
@neatlogs.span(kind="GUARDRAIL")      # REMOVE
async def input_guardrail_fn(ctx, agent, input_text):
    ...

# ✅ SHOULD BE — no decorator; the SDK guardrail is auto-traced
async def input_guardrail_fn(ctx, agent, input_text):
    ...
```

## Custom (non-SDK) tools

If the project has standalone helper functions that perform I/O but are NOT registered as `@function_tool` and NOT invoked through the Agents SDK, those MAY get `@neatlogs.span(kind="TOOL", ...)`. This is rare — in an Agents SDK app virtually all tools go through `@function_tool`.

## Verification

- [ ] Grep `@function_tool` — none have a neatlogs decorator.
- [ ] Grep `Agent(` and agent factories — none have `@neatlogs.span()`.
- [ ] Guardrail functions / `@input_guardrail` / `@output_guardrail` — none have a neatlogs decorator.
- [ ] `handoff(...)` constructs — untouched.
- [ ] The only `@neatlogs.span(kind="WORKFLOW")` is on the `Runner.run()` caller.
