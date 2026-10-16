# Step 1: Detect LangSmith (direct vs transitive)

## Action

1. Find all Python source files that import `langsmith` directly:
   ```bash
   grep -rln --include='*.py' -E '^\s*(from\s+langsmith\s|import\s+langsmith\b)' . 2>/dev/null
   ```
2. Find all places that use the OTel env vars that look LangSmith-shaped,
   OR that enable LangChain auto-tracing:
   ```bash
   grep -rln --include='*.py' --include='*.env*' --include='*.yaml' --include='*.yml' \
     -E 'OTEL_EXPORTER_OTLP_ENDPOINT.*langchain|OTEL_EXPORTER_OTLP_ENDPOINT.*smith|LANGCHAIN_(TRACING|API|ENDPOINT|PROJECT)|LANGSMITH_(TRACING|API|ENDPOINT|PROJECT)' . 2>/dev/null
   ```
3. Check `pyproject.toml` / `requirements*.txt` for `langsmith` as a
   declared dep (vs. a transitive dep pulled in by a framework extra):
   ```bash
   grep -E '^\s*langsmith(\s*[=><~]|$)' pyproject.toml requirements*.txt setup.py 2>/dev/null
   ```
   If `langsmith` is in the project's `pyproject.toml` `[project] dependencies` /
   `[tool.poetry.dependencies]` / `requirements.txt` / `setup.py
   install_requires` → **direct dep**. Otherwise → **transitive** (do
   not uninstall blindly in step 6).
4. Detect which LangChain surface is the entry point (Path A vs
   Path B):
   ```bash
   # Path A: LangChain's observability callback is auto-registered
   # when LANGSMITH_TRACING_V2=true. The langchain-observation
   # is patched into LangChain's runtime.
   grep -rln --include='*.py' -E 'from\s+langchain\.(observability|tracing|callbacks)' . 2>/dev/null
   # Path B: explicit @traceable / RunTree usage
   grep -rln --include='*.py' -E 'from\s+langsmith\s+import\s+(traceable|trace)|RunTree\(|langsmith_client' . 2>/dev/null
   ```

## What you learn

- **Files in step 1's grep result** are the call sites you need to
  touch in step 5 (Path B) OR confirm unchanged (Path A).
- **`pyproject.toml` listing** tells you whether it's a real dep or a
  transitive one. If transitive, **LangSmith is probably being used
  by a framework you depend on** (almost always LangChain). Don't
  uninstall without first checking the framework's docs.
- **The two `grep -rln` results in step 4** tell you which LangChain
  surface is in use. Path A is auto-tracing (env-var-gated). Path B
  is explicit `@traceable` or `RunTree` calls in the source.
- **If the project uses LangChain** (which is most LangSmith users
  today), the migration is mostly about the LangChain entry point.
  Check `from langchain.observability import ...` (v0.3+) or
  `langchain.tracing_context(...)` (v0.2).

## Two-source rule

If step 1 finds BOTH `from langsmith import` AND a LangChain
auto-tracing env var, the project is hybrid — some modules route
through the explicit SDK, others through LangChain's auto-tracing.
Handle BOTH: do step 4 for the auto-traced spans, then do step 5
for the explicit-SDK call sites.

## Edge case: framework extras

LangChain's auto-tracing pulls `langsmith` in as a transitive dep
when `LANGSMITH_TRACING_V2=true` is set. If `langsmith` is NOT in
your top-level `pyproject.toml` but IS importable, LangChain is
auto-instrumenting on your behalf. In that case, the correct
migration is to:

1. Add `neatlogs` as a direct dep + `neatlogs.init(...)` (step 3).
2. Disable LangSmith auto-tracing (`unset LANGSMITH_TRACING_V2`).
3. Re-point the LangChain observability callback to NeatLogs —
   LangChain's `langchain.observability` callback accepts a custom
   tracer provider; pass NeatLogs' via the `langchainHandler` (or
   set `OTEL_EXPORTER_OTLP_ENDPOINT=...neatlogs...` to bypass the
   callback and let OTel route directly).
4. Do not uninstall `langsmith` in step 6 — it stays as a
   transitive dep but no longer receives traces.

## Verify BEFORE moving to step 2

1. You have a list of files using `from langsmith import ...`.
2. You have a list of files / configs containing
   `LANGCHAIN_TRACING_V2` / `LANGSMITH_*` or
   `OTEL_EXPORTER_OTLP_ENDPOINT=*langchain*` / `*smith*`.
3. You have classified the project as Path A (LangChain auto-
   tracing), Path B (explicit `@traceable` / `RunTree`), or hybrid.
