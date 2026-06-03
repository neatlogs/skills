# Step 5: Combine wrap() with @span / trace / log

Use the manual primitives for YOUR orchestration code. The DSPy module's CHAIN/LLM spans nest under whatever span is active.

## Do NOT wrap a single module call in its own span

A function that only calls the pipeline once is not a meaningful CHAIN of YOUR code — and the DSPy module already emits its own CHAIN span. Wrapping it adds an empty duplicate layer. Let the module's span nest directly under the WORKFLOW and log in the workflow.

```python
import neatlogs

@neatlogs.span(kind="WORKFLOW", name="qa_session")
def main():
    pipeline = QAPipeline()
    neatlogs.wrap(pipeline)
    with neatlogs.trace("qa_session"):
        for q in questions:
            neatlogs.log("answering: {q}", q=q)
            result = pipeline(question=q)        # dspy CHAIN/LLM spans nest under WORKFLOW
            neatlogs.log("done", )
```

Hierarchy: `WORKFLOW(qa_session) > CHAIN(dspy module) > LLM`.

## Use CHAIN only for REAL multi-step work

`kind="CHAIN"` is correct when YOUR function chains several stages around the module call — e.g. fetch data, run the pipeline, validate/format:

```python
@neatlogs.span(kind="CHAIN", name="graded_answer")
def graded_answer(pipeline, question: str) -> str:
    facts = lookup_facts(question)               # step 1
    result = pipeline(question=question, context=facts)  # step 2 (dspy span nests here)
    return grade_and_format(result.answer)       # step 3
```

If the function is a one-line pass-through to `pipeline(...)`, don't decorate it.

- `@neatlogs.span(kind="WORKFLOW")` — the user-facing entry point.
- `@neatlogs.span(kind="CHAIN")` — YOUR functions that chain several real steps, not a single module call.
- `neatlogs.trace("name")` — group operations / prompt templates.
- `neatlogs.log("msg {k}", k=v)` — steps inside a span.
