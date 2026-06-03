# Span kinds (DSPy)

`neatlogs.wrap()` emits:
- **CHAIN** — every `dspy.Module.__call__` (Predict / ChainOfThought / ReAct / your subclass), nested
- **LLM** — `dspy.LM.__call__` (the model request)
- **RETRIEVER** — `dspy.Retrieve.__call__`

Your own code: `@neatlogs.span(kind="WORKFLOW"|"CHAIN"|"TOOL"|...)`.
