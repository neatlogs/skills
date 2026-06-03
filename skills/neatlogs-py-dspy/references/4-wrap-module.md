# Step 4: Wrap a DSPy module with neatlogs.wrap()

`neatlogs.wrap()` installs GLOBAL DSPy class hooks. Call it once on the top-level module (or any module/Predict instance) — every nested module + LM call is then traced.

```python
import neatlogs

pipeline = QAPipeline()          # your dspy.Module subclass
neatlogs.wrap(pipeline)          # installs class hooks (idempotent, global)

result = pipeline(question="Why is the sky blue?")
```

Produces:
```
CHAIN  dspy.QAPipeline
  ↳ CHAIN  dspy.Predict / dspy.ChainOfThought
      ↳ LLM  dspy.lm
```

## Rules
- One `wrap()` call suffices (hooks are global). Wrapping the top module is enough.
- Subclasses of `dspy.Module` (your custom pipelines) are detected correctly.
