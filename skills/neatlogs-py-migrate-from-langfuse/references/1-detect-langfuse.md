# Step 1: Detect Langfuse (direct vs transitive)

## Action

1. Find all Python source files that import `langfuse` directly:
   ```bash
   grep -rln --include='*.py' -E '^\s*(from\s+langfuse\s|import\s+langfuse\b)' . 2>/dev/null
   ```
2. Find all places that use the OTel env vars that look Langfuse-shaped:
   ```bash
   grep -rln --include='*.py' --include='*.env*' --include='*.yaml' --include='*.yml' \
     -E 'OTEL_EXPORTER_OTLP_ENDPOINT.*langfuse|LANGFUSE_(PUBLIC|SECRET|HOST)' . 2>/dev/null
   ```
3. Check `pyproject.toml` / `requirements*.txt` for `langfuse` as a
   declared dep (vs. a transitive dep pulled in by a framework extra):
   ```bash
   grep -E '^\s*langfuse(\s*[=><~]|$)' pyproject.toml requirements*.txt setup.py 2>/dev/null
   ```
   If `langfuse` is in the project's `pyproject.toml` `[project] dependencies` /
   `[tool.poetry.dependencies]` / `requirements.txt` / `setup.py
   install_requires` → **direct dep**. Otherwise → **transitive** (do
   not uninstall blindly in step 6).

## What you learn

- **Files in step 1's grep result** are the call sites you need to
  touch in step 5 (Path B, native SDK) OR confirm unchanged (Path A,
  OTel).
- **`pyproject.toml` listing** tells you whether it's a real dep or a
  transitive one. If transitive, **Langfuse is probably being used by
  a framework you depend on** (e.g. LangChain's optional Langfuse
  callback handler). Don't uninstall without first checking the
  framework's docs.
- **`OTEL_EXPORTER_OTLP_ENDPOINT=...langfuse...` matches** → you are on
  Path A (OTel exporter). Step 4 is sufficient; you can SKIP step 5.

## Two-source rule

If step 1 finds BOTH a `from langfuse import` AND a Langfuse-shaped
OTel env var, the project is hybrid — some modules route through
the native SDK, others through OTel. Handle BOTH: do step 4 for the
OTel-routed spans, then do step 5 for the native-SDK call sites.

## Edge case: framework extras

Some frameworks (LangChain, LlamaIndex, CrewAI) ship optional
Langfuse integrations pulled in as transitive deps. If `langfuse` is
NOT in your top-level `pyproject.toml` but IS importable, the project
is probably using one of these optional integrations, and the call
site is in the framework's adapter code, not yours. In that case, the
correct migration is to:

1. Add `neatlogs` as a direct dep + `neatlogs.init(...)` (step 3).
2. Re-point the framework's tracing to NeatLogs — usually one env
   var (e.g. LangChain has `LANGCHAIN_TRACING_V2` + an exporter
   endpoint; point that at NeatLogs in step 4).
3. Do not uninstall `langfuse` in step 6 — it stays as a transitive
   dep but no longer receives traces.

## Verify BEFORE moving to step 2

1. You have a list of files using `from langfuse import ...`.
2. You have a list of files / configs containing `LANGFUSE_*` or
   `OTEL_EXPORTER_OTLP_ENDPOINT=*langfuse*`.
3. You have classified the project as Path A (OTel only), Path B
   (native SDK only), or hybrid.
