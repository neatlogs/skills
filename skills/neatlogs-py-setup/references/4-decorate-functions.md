# Step 4: Identify and Decorate Functions

## The One Rule That Matters Most

Ask yourself for EVERY function: **"Is this function directly triggered by the user (CLI command, HTTP endpoint, job), or is it internal?"**

- User-triggered → `@span(kind="WORKFLOW")` — this is the TRACE ROOT
- Internal orchestrator (calls other functions but no LLM call itself) → `@span(kind="CHAIN")`
- Contains an LLM API call → `@span(kind="CHAIN")`
- Discrete I/O or tool capability → `@span(kind="TOOL")` [Step 6]

## WRONG vs RIGHT — Classification

```python
# ❌ WRONG — run_pipeline is NOT a WORKFLOW. It's internal. Nobody calls it directly.
@neatlogs.span(kind="WORKFLOW")
def run_pipeline(text, settings):
    return asyncio.run(process_document(text, settings))

# ❌ WRONG — process_document is NOT a WORKFLOW. It's an internal orchestrator.
@neatlogs.span(kind="WORKFLOW")
async def process_document(text, settings):
    chunks = chunk_text(text)
    results = await asyncio.gather(...)
    return combine(results)

# ✅ RIGHT — the click command IS the user-facing entry point. THIS is the WORKFLOW.
@cli.command()
@click.argument("file_path")
@neatlogs.span(kind="WORKFLOW", name="process")
def process(file_path: str):
    text = read_document(file_path)
    result = run_pipeline(text, settings)
    write_document(result.report, output_path)

# ✅ RIGHT — internal orchestrators are CHAIN
@neatlogs.span(kind="CHAIN", name="run_pipeline")
def run_pipeline(text, settings):
    return asyncio.run(process_document(text, settings))

@neatlogs.span(kind="CHAIN", name="process_document")
async def process_document(text, settings):
    chunks = chunk_text(text)
    results = await asyncio.gather(...)
    return combine(results)
```

## Why This Matters: Trace Context Binding

All spans in one execution MUST share one trace. Spans inherit their parent's trace context. If a decorated function is called from an UNDECORATED function, it starts a NEW orphan trace.

```
# What happens WITHOUT decorating the CLI command:
process() [no span]
  ├── read_document()  → orphan trace A (lost!)
  ├── run_pipeline()   → orphan trace B
  └── write_document() → orphan trace C (lost!)

# What happens WITH the CLI command as WORKFLOW:
process() [WORKFLOW span — trace root]
  ├── read_document()  → child of process (same trace!)
  ├── run_pipeline()   → child of process (same trace!)
  │     └── process_document() → grandchild (same trace!)
  └── write_document() → child of process (same trace!)
```

## Decision Tree

For each function, answer in order:

1. **Is it the user-facing entry point?** (click command, FastAPI route, celery task, `main()`)
   → YES → `@span(kind="WORKFLOW")`

2. **Does it contain a direct LLM API call?** (client.chat.completions.create, etc.)
   → YES → `@span(kind="CHAIN")` (see Step 5 for trace() wrapper)
   Exception: skip if the function ONLY does `return client.chat.completions.create(...)` with zero other logic.

3. **Does it orchestrate multiple child functions without an LLM call?**
   → YES → `@span(kind="CHAIN")`

4. **Does it do discrete I/O / external API?**
   → YES → `@span(kind="TOOL")` (handled in Step 6)

5. **Is it a pure utility?** (formatting, config, <3 lines, no I/O)
   → NO decorator

## Decorator Placement with Click/Typer

```python
# @neatlogs.span goes BELOW all click decorators, ABOVE def:
@cli.command()
@click.argument("file_path")
@click.option("--output", "-o", default=None)
@neatlogs.span(kind="WORKFLOW", name="process")
def process(file_path: str, output: str | None):
    ...
```

## Decorator Placement with @retry

```python
# @neatlogs.span goes BELOW @retry, closest to def:
@retry(stop=stop_after_attempt(3))
@neatlogs.span(kind="CHAIN", name="summarize_chunk")
async def summarize_chunk(text, settings):
    ...
```

## Action

1. Read ALL source files from the entry point outward.
2. For each CLI command / endpoint / job → add `@span(kind="WORKFLOW")`.
3. For each internal function with an LLM call → add `@span(kind="CHAIN")`.
4. For each internal orchestrator (no LLM, calls children) → add `@span(kind="CHAIN")`.
5. Add `import neatlogs` to each file that gets decorators.

## Verify BEFORE moving to step 5

1. Every CLI command / route handler has `@span(kind="WORKFLOW")`. Count them — if there are 3 commands, there must be 3 WORKFLOW spans.
2. No internal function (run_pipeline, process_document, process_chunk) has kind="WORKFLOW". These are CHAIN.
3. The WORKFLOW span is the outermost decorated function — all other spans are called beneath it.
