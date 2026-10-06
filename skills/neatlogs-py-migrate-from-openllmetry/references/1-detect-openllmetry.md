# Step 1: Detect OpenLLMetry (direct vs transitive)

## Action

1. Find all Python source files that import OpenLLMetry or
   OpenInference packages directly:
   ```bash
   grep -rln --include='*.py' -E '^\s*(from\s+(opentelemetry|openinference|openllmetry)\s|import\s+(opentelemetry|openinference|openllmetry)\b)' . 2>/dev/null
   ```
2. Find all places that set OTel env vars (any OTel collector, not
   just one pointing at OpenLLMetry):
   ```bash
   grep -rln --include='*.py' --include='*.env*' --include='*.yaml' --include='*.yml' \
     -E 'OTEL_EXPORTER_OTLP_(ENDPOINT|HEADERS)|OTEL_SERVICE_NAME|OTEL_RESOURCE_ATTRIBUTES' . 2>/dev/null
   ```
3. Check `pyproject.toml` / `requirements*.txt` for OpenLLMetry
   packages as a declared dep (vs. transitive):
   ```bash
   grep -E '^\s*(opentelemetry|openinference|openllmetry)(\s|[=><~]|$)' pyproject.toml requirements*.txt setup.py 2>/dev/null
   ```
   If `opentelemetry-instrumentation-*` (or any `openinference-*`)
   is in the project's `pyproject.toml` `[project] dependencies` /
   `[tool.poetry.dependencies]` / `requirements.txt` / `setup.py
   install_requires` → **direct dep**. Otherwise → **transitive**
   (do not uninstall blindly in step 6).
4. Detect which OpenLLMetry surface is the entry point (Path A vs
   Path B):
   ```bash
   # Path A: auto-instrumentation — opentelemetry-instrumentation-* in deps,
   # the user is relying on OTel's monkey-patching of supported libs.
   grep -rln --include='*.py' -E 'opentelemetry\.instrumentation\.(openai|anthropic|google|cohere|mistral|bedrock|llamaindex|langchain)' . 2>/dev/null
   # Path B: manual tracer + start_as_current_span
   grep -rln --include='*.py' -E 'trace\.get_tracer\(|start_as_current_span\(|BatchSpanProcessor\(|set_attribute\(' . 2>/dev/null
   ```

## What you learn

- **Files in step 1's grep result** are the call sites you need to
  touch in step 5 (Path B) or confirm unchanged (Path A).
- **`pyproject.toml` listing** tells you whether it's a real dep or
  a transitive one. If transitive, **OpenLLMetry is probably
  being used by a framework you depend on** (LlamaIndex, LangChain
  extras, Phoenix adapters). Don't uninstall without first
  checking the framework's docs.
- **The two `grep -rln` results in step 4** tell you which surface
  is in use. Path A is auto-instrumentation (env-var-gated). Path
  B is manual `tracer.start_as_current_span` calls in the source.
- **The `BatchSpanProcessor` grep** is the strongest Path B
  signal: if a project has its own `BatchSpanProcessor` chain,
  it's using the OTel SDK directly and is Path B.

## Two-source rule

If step 1 finds BOTH `opentelemetry-instrumentation-*` imports AND
manual `tracer.start_as_current_span` calls, the project is hybrid
— some modules route through auto-instrumentation, others through
manual spans. Handle BOTH: do step 4 for the auto-instrumented
spans, then do step 5 for the manual call sites.

## Edge case: framework extras

LlamaIndex and LangChain ship optional OpenLLMetry
integrations. If `opentelemetry-instrumentation-openai` (or
similar) is NOT in your top-level `pyproject.toml` but IS
importable, the framework is auto-instrumenting on your behalf.
In that case, the correct migration is to:

1. Add `neatlogs` as a direct dep + `neatlogs.init(...)` (step 3).
2. Re-point the framework's OTel exporter to NeatLogs — usually
   one env var (`OTEL_EXPORTER_OTLP_ENDPOINT` and the
   `OTEL_EXPORTER_OTLP_HEADERS` pair).
3. Do not uninstall `opentelemetry-instrumentation-*` in step 6
   — it stays as a transitive dep but no longer receives traces
   (or it does, as a side-effect of side-by-side mode until
   step 6 cuts over).

## Verify BEFORE moving to step 2

1. You have a list of files using
   `from opentelemetry...` / `from openinference...` / `from openllmetry...`.
2. You have a list of files / configs containing
   `OTEL_EXPORTER_OTLP_*` or `OTEL_RESOURCE_ATTRIBUTES`.
3. You have classified the project as Path A
   (auto-instrumentation), Path B (manual `tracer.start_as_current_span`),
   or hybrid.
