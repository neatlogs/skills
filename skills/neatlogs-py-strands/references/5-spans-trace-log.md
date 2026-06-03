# Step 5: Combine with @span / trace / log

Use the manual primitives for YOUR orchestration code. The native Strands spans (invoke_agent / model / execute_tool) nest under whatever span is active.

## Do NOT wrap a single agent call in its own span

A function that only calls `agent(question)` once is not a CHAIN — nothing is chained, and Strands already emits its own agent span. `@neatlogs.span(kind="CHAIN")` around it just adds an empty layer. Log in the WORKFLOW and let the native agent span nest directly under it.

```python
import neatlogs

@neatlogs.span(kind="WORKFLOW", name="math_session")
def main():
    agent = neatlogs.strands_hooks(build_agent())
    with neatlogs.trace("math_session"):
        for q in questions:
            neatlogs.log("asking: {q}", q=q)
            answer = str(agent(q))       # native agent/llm/tool spans nest under WORKFLOW
            neatlogs.log("done")
```

Hierarchy: `WORKFLOW(math_session) > agent(invoke_agent) > llm / tool`.

## Use CHAIN only for REAL multi-step work

`kind="CHAIN"` is correct when YOUR function chains several stages around the agent call — e.g. prepare input, call the agent, post-process:

```python
@neatlogs.span(kind="CHAIN", name="solve_and_verify")
def solve_and_verify(agent, problem: str) -> str:
    normalized = normalize(problem)      # step 1
    answer = str(agent(normalized))      # step 2 (native agent span nests here)
    return verify(answer)                # step 3
```

If the function is a one-line pass-through to `agent(...)`, don't decorate it.

- `@neatlogs.span(kind="WORKFLOW")` — the user-facing entry point.
- `@neatlogs.span(kind="CHAIN")` — YOUR functions that chain several real steps, not a single agent call.
- `neatlogs.trace("name")` — group operations.
- `neatlogs.log("msg {k}", k=v)` — steps inside a span.
