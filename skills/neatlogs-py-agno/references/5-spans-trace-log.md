# Step 5: Combine wrap() with @span / trace / log

Use the manual primitives for YOUR orchestration code. The wrapper's AGENT/LLM/TOOL spans nest under whatever span is active.

## Do NOT wrap a single agent call in its own span

A function that only calls `agent.run()` once (with logging) is not a CHAIN — nothing is chained. `@neatlogs.span(kind="CHAIN")` around it just inserts an empty layer above the AGENT span. Let the AGENT span nest directly under the WORKFLOW and log in the workflow.

```python
import neatlogs

agent = neatlogs.wrap(support_agent)

@neatlogs.span(kind="WORKFLOW", name="support_session")
def main():
    with neatlogs.trace("support_session"):
        for q in questions:
            neatlogs.log("handling: {q}", q=q)
            resp = agent.run(q)          # AGENT/LLM/TOOL spans nest under WORKFLOW
            neatlogs.log("done")
```

Hierarchy: `WORKFLOW(support_session) > AGENT(agno.agent.run) > LLM/TOOL`.

## Use CHAIN only for REAL multi-step work

`kind="CHAIN"` is correct when YOUR function chains several stages around the agent call — e.g. look up an order, run the agent, then post-process:

```python
@neatlogs.span(kind="CHAIN", name="resolve_ticket")
def resolve_ticket(question: str) -> str:
    order = lookup_order(question)       # step 1
    resp = agent.run(f"{order}\n\n{question}")   # step 2 (AGENT nests here)
    return summarize(resp.content)       # step 3
```

If the function is a one-line pass-through to `agent.run(...)`, don't decorate it.

- `@neatlogs.span(kind="WORKFLOW")` — the user-facing entry point.
- `@neatlogs.span(kind="CHAIN")` — YOUR functions that chain several real steps, not a single agent call.
- `neatlogs.trace("name")` — group operations / prompt templates.
- `neatlogs.log("msg {k}", k=v)` — steps inside a span.
