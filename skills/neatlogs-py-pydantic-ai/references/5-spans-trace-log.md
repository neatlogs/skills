# Step 5: Combine wrap() with @span / trace / log

Use the manual primitives for YOUR orchestration code. The wrapper's AGENT/LLM/TOOL spans nest under whatever span is active.

## Do NOT wrap a single agent call in its own span

A function that only calls the agent once (with some logging) is NOT a CHAIN — nothing is being chained. Adding `@neatlogs.span(kind="CHAIN")` around it just inserts an empty layer between the WORKFLOW and the AGENT span. Let the agent's AGENT span nest directly under the WORKFLOW, and put the logs in the workflow.

```python
import neatlogs

agent = neatlogs.wrap(research_agent)

@neatlogs.span(kind="WORKFLOW", name="research_session")
def main():
    with neatlogs.trace("research_session"):     # groups the turns / attaches templates
        for q in questions:
            neatlogs.log("running query: {q}", q=q)
            result = agent.run_sync(q)           # AGENT/LLM/TOOL spans nest under WORKFLOW
            neatlogs.log("done, length {n}", n=len(result.output))
```

Resulting hierarchy:
```
WORKFLOW research_session
  ↳ AGENT pydantic_ai.agent.run_sync
      ↳ LLM / TOOL
```

## Use CHAIN only for REAL multi-step work

`kind="CHAIN"` is correct when the function performs several sequential steps — e.g. retrieve context, call the agent, then post-process. There the CHAIN span is meaningful because it brackets genuine chained stages:

```python
@neatlogs.span(kind="CHAIN", name="answer_with_context")
def answer_with_context(question: str) -> str:
    docs = retrieve_docs(question)               # step 1
    answer = agent.run_sync(f"{context(docs)}\n\n{question}").output  # step 2 (AGENT nests here)
    return postprocess(answer)                   # step 3
```

Rule of thumb: if removing the decorated function would lose a meaningful processing boundary, it earns a span. If it's a one-line pass-through to the agent, don't decorate it.

## When to use which
- `@neatlogs.span(kind="WORKFLOW")` — the user-facing entry point (trace root).
- `@neatlogs.span(kind="CHAIN")` — YOUR functions that chain several real steps. NOT a single agent call.
- `@neatlogs.span(kind="TOOL"|"RETRIEVER"|...)` — your own discrete tool / retrieval functions not managed by the framework.
- `neatlogs.trace("name")` — group multiple operations, or attach prompt templates.
- `neatlogs.log("msg {k}", k=v)` — record a step/event inside the current span.
