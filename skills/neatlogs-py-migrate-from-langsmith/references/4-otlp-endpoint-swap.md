# Step 4: OTLP-endpoint swap — the 90% path

## Why this is the headline

If step 1 classified you as **Path A (LangChain auto-tracing via
OTel)** — i.e. your project sets `LANGSMITH_TRACING_V2=true` (or
the older `LANGCHAIN_TRACING_V2=true`) and uses the
`langchain.observability` callback — the entire migration is
**2 environment variables**. No code changes.

Path A covers the majority of LangSmith users: anyone using
LangChain with auto-tracing enabled, anyone using the OTel SDK
with `OTLPSpanExporter` pointing at LangSmith's collector, and
the `langchain.tracing` context manager. Most LangChain tutorials
default to Path A.

## Action

1. Find the current OTel env vars and the LangSmith env vars:
   ```bash
   grep -rE 'OTEL_EXPORTER_OTLP_(ENDPOINT|HEADERS)|LANGSMITH_(TRACING|API|ENDPOINT|PROJECT)|LANGCHAIN_(TRACING|API|ENDPOINT|PROJECT)' . \
     --include='.env*' --include='*.env*' --include='*.yaml' --include='*.yml' --include='*.json' 2>/dev/null
   ```
2. Update them to point at NeatLogs.

   **Before (LangSmith):**
   ```bash
   OTEL_EXPORTER_OTLP_ENDPOINT=https://api.smith.langchain.com
   OTEL_EXPORTER_OTLP_HEADERS=x-api-key=${LANGSMITH_API_KEY}
   LANGSMITH_TRACING_V2=true
   LANGSMITH_API_KEY=lsv2_pt_...
   LANGCHAIN_PROJECT=my-app
   ```
   (Older LangChain v0.2 used `LANGCHAIN_TRACING_V2` /
   `LANGCHAIN_API_KEY` / `LANGCHAIN_ENDPOINT` instead of the
   `LANGSMITH_*` ones. Same idea, different names.)

   **After (NeatLogs):**
   ```bash
   OTEL_EXPORTER_OTLP_ENDPOINT=https://ingest.neatlogs.com
   OTEL_EXPORTER_OTLP_HEADERS=x-api-key=${NEATLOGS_API_KEY}
   NEATLOGS_API_KEY=nl_...
   ```
   Notes:
   - The NeatLogs endpoint is `/v1/traces` — the OTel SDK appends
     the path itself when you set the endpoint without a path.
     Some OTel versions require an explicit path; if you see
     404s, set
     `OTEL_EXPORTER_OTLP_ENDPOINT=https://ingest.neatlogs.com/v1/traces`
     directly.
   - The auth header is `x-api-key: <value>`, NOT
     `Authorization: Bearer`.
   - URL-encode the `=` and `:` in the value when using a header
     dict string; the OTel SDK also accepts a comma-separated
     `k1=v1,k2=v2` form.
3. **Set `LANGCHAIN_PROJECT` / `LANGSMITH_PROJECT` to your
   `workflow_name`** if it was already in use. The project name
   shows up in NeatLogs as the Workflow column. If you don't
   set it, traces still land — but with the SDK default.
4. If you have a `requirements.txt` / `pyproject.toml` that
   hardcodes the LangSmith endpoint, update it too.
5. If step 2 added a second OTel exporter for NeatLogs (the
   side-by-side pattern), REMOVE the second exporter — the
   endpoint swap now sends the same spans to NeatLogs. The
   first exporter (the one for LangSmith) stays; that's the
   side-by-side.

## What you learn

- Path A is now done. Traces flow into both LangSmith and
  NeatLogs.
- The dashboard for NeatLogs starts receiving spans at this
  point. Verify by triggering a request and checking the
  NeatLogs dashboard for a new trace within ~10 seconds.

## When to skip step 4

If step 1 classified you as **Path B (explicit `@traceable` SDK)**
— the project calls `from langsmith import traceable` and uses
`RunTree` directly — step 4 alone is not enough. The LangSmith
SDK does not use OTel for the trace tree, so re-pointing
`OTEL_EXPORTER_OTLP_ENDPOINT` does not change where the
LangSmith spans go (they go to LangSmith's hosted collector via
the SDK's own HTTP client).

In that case, do step 5 to replace the explicit SDK call sites.
You can still ALSO do step 4 if the project has OTel-routed
spans from some other instrumentation layer (e.g. an HTTP
client instrumentor).

## LangChain auto-tracing caveat

Even after step 4, if `LANGSMITH_TRACING_V2=true` is still set,
LangChain's `langchain.observability` callback continues to run
its own internal tracer in parallel with the OTel route. The
LangChain tracer still sends to LangSmith (its own client, not
OTel). The OTel route you've now re-pointed to NeatLogs is a
SECOND copy of the same spans.

This is the side-by-side mode. It's expected. Step 6 (cutover)
disables the LangSmith tracer by unsetting `LANGSMITH_TRACING_V2`.

## Verify BEFORE moving to step 5 (or step 6)

1. Trigger a request; verify a new trace appears in the NeatLogs
   dashboard within 10 seconds. (Use a simple GET or run a
   known test case.)
2. Confirm the trace has the right shape: spans nested, tool
   calls recorded, prompts visible. If a span is missing, the
   OTel instrumentation might be filtered — check
   `OTEL_PYTHON_LOG_CORRELATION` and LangChain's tracer config
   (LangChain's callback may filter spans that don't match its
   expected schema).
3. Path A is now done; you can SKIP step 5 and go to step 6.
