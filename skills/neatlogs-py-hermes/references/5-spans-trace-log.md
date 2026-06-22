# Step 5: Combine the instrumentation with @span / trace / log

Use the manual primitives for YOUR orchestration code. The hermes AGENT/LLM/TOOL
spans nest under whatever span is active.

## Do NOT wrap a single agent call in its own span

A function that only calls `agent.run_conversation()` once (with logging) is not a
CHAIN — nothing is chained. `@neatlogs.span(kind="CHAIN")` around it just inserts
an empty layer above the AGENT span. Let the AGENT span nest directly under the
WORKFLOW and log in the workflow.

```python
import neatlogs

@neatlogs.span(kind="WORKFLOW", name="research_session")
def main():
    with neatlogs.trace("research_session"):
        for q in questions:
            neatlogs.log("handling: {q}", q=q)
            resp = agent.run_conversation(q)   # AGENT/LLM/TOOL nest under WORKFLOW
            neatlogs.log("done")
```

Hierarchy: `WORKFLOW(research_session) > AGENT(hermes.run_conversation) > LLM/TOOL`.

## Use CHAIN only for REAL multi-step work

`kind="CHAIN"` is correct when YOUR function chains several stages around the agent
call — e.g. fetch context, run the agent, then post-process:

```python
@neatlogs.span(kind="CHAIN", name="answer_with_context")
def answer_with_context(question: str) -> str:
    ctx = fetch_context(question)                     # step 1
    resp = agent.run_conversation(f"{ctx}\n\n{question}")  # step 2 (AGENT nests here)
    return summarize(resp)                            # step 3
```

If the function is a one-line pass-through to `agent.run_conversation(...)`, don't
decorate it.

- `@neatlogs.span(kind="WORKFLOW")` — the user-facing entry point.
- `@neatlogs.span(kind="CHAIN")` — YOUR functions that chain several real steps.
- `neatlogs.trace("name")` — group operations / prompt templates.
- `neatlogs.log("msg {k}", k=v)` — steps inside a span.
