---
name: neatlogs-py-dspy
description: Use when adding neatlogs observability to a Python project that uses DSPy (imports `dspy`, defines `dspy.Module`s / signatures).
compatibility: Neatlogs Wizard Agent
metadata:
  author: neatlogs
  version: "1.0"
  language: python
  framework: dspy
---

# Neatlogs Python Setup — DSPy

This project uses **DSPy** (`dspy.Module`, `dspy.Predict`, `dspy.ChainOfThought`, `dspy.ReAct`). Neatlogs instruments it with **`neatlogs.wrap(module)`**.

## Core mechanism — `neatlogs.wrap(module)`

`neatlogs.wrap()` installs DSPy class-level hooks (idempotent, global), so passing ANY module instance — including your own `dspy.Module` subclass — patches every module call, nested. Span tree:

```
CHAIN  dspy.Module.__call__   (Predict / ChainOfThought / ReAct / custom — every module call, nested)
  ↳ LLM        dspy.LM.__call__       (the underlying model request)
  ↳ RETRIEVER  dspy.Retrieve.__call__ (if used)
```

Combine with `@neatlogs.span` / `neatlogs.trace` / `neatlogs.log` for your own orchestration. The DSPy CHAIN/LLM spans nest under your manual spans.

## Steps

1. **Install** → `references/1-install.md`
2. **Add init()** → `references/2-add-init.md`
3. **Set environment variables** → `references/3-set-env.md`
4. **Wrap a DSPy module with neatlogs.wrap()** → `references/4-wrap-module.md`
5. **Add @span / trace / log to orchestration** → `references/5-spans-trace-log.md`
6. **Lifecycle (flush/shutdown)** → `references/6-flush-shutdown.md`

## Rules (apply to ALL steps)

- `neatlogs.init()` MUST run BEFORE importing `dspy` (so class hooks patch at the right time). `load_dotenv()` runs before `init()`.
- **Use `neatlogs.wrap(module)`, NOT `instrumentations=["dspy"]`.** `wrap()` patches DSPy's classes directly and works on ANY DSPy version. The `instrumentations=["dspy"]` path uses the OpenInference DSPy instrumentor, which **requires DSPy ≥ 2.6.0 and silently emits no spans on older DSPy** — so prefer `wrap()`, especially when the project pins DSPy < 2.6.
- `neatlogs.wrap(module)` installs GLOBAL DSPy class hooks — calling it once on any module instance traces ALL module/LM calls. Wrapping the top-level pipeline module is enough.
- `wrap()` returns the module unchanged; you can keep using your existing variable.
- Do NOT wrap a single module call in `@span`/`trace` — the CHAIN span is created by the hook. Use `@span` for YOUR orchestration only.
- Never hardcode API keys — use `os.getenv()`.
- `import neatlogs` at module top level.

## Reference
- Combining wrap() with @span/trace/log → `references/5-spans-trace-log.md`
- Span kinds reference → `references/span-kinds.md`
