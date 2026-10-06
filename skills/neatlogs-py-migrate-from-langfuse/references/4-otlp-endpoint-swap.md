# Step 4: OTLP-endpoint swap — the 90% path

## Why this is the easy path

If step 1 classified you as **Path A (OTel exporter)** — i.e. your
project already routes traces through the OpenTelemetry SDK to a
Langfuse-shaped endpoint — the entire migration is **2 environment
variables**. No code changes.

Path A covers the majority of Langfuse v2 users: framework callbacks
(LangChain, LlamaIndex, CrewAI) ship with OTel exporters; people using
`opentelemetry-instrumentation-*` packages; anyone using the OTel
SDK directly with `OTLPSpanExporter` pointing at Langfuse.

## Action

1. Find the current OTel env vars:
   ```bash
   grep -rE 'OTEL_EXPORTER_OTLP_(ENDPOINT|HEADERS)' . --include='.env*' --include='*.env*' --include='*.yaml' --include='*.yml' --include='*.json' 2>/dev/null
   ```
2. Update them to point at NeatLogs.

   **Before (Langfuse):**
   ```bash
   OTEL_EXPORTER_OTLP_ENDPOINT=https://cloud.langfuse.com/api/otel/v1/traces
   OTEL_EXPORTER_OTLP_HEADERS=Authorization=Bearer%20${LANGFUSE_PUBLIC_KEY}%3A${LANGFUSE_SECRET_KEY}
   ```

   **After (NeatLogs):**
   ```bash
   OTEL_EXPORTER_OTLP_ENDPOINT=https://ingest.neatlogs.com
   OTEL_EXPORTER_OTLP_HEADERS=x-api-key=${NEATLOGS_API_KEY}
   ```
   Notes:
   - The NeatLogs endpoint is `/v1/traces` at `/v1/traces` over OTLP/HTTP —
     the OTel SDK appends the path itself when you set the endpoint
     without a path. Some OTel versions require an explicit path; if
     you see 404s, set `OTEL_EXPORTER_OTLP_ENDPOINT=https://ingest.neatlogs.com/v1/traces`
     directly.
   - The auth header is `x-api-key: <value>`, NOT `Authorization: Bearer`.
   - URL-encode the `=` and `:` in the value when using a header dict
     string; the OTel SDK also accepts a comma-separated `k1=v1,k2=v2`
     form.
3. If you have a `requirements.txt` / `pyproject.toml` that hardcodes
   the Langfuse endpoint, update it too.
4. If step 2 added a second OTel exporter for NeatLogs (the
   side-by-side pattern), REMOVE the second exporter — the endpoint
   swap now sends the same spans to NeatLogs. The first exporter (the
   one for Langfuse) stays; that's the side-by-side.

## What you learn

- Path A is now done. Traces flow into both Langfuse and NeatLogs.
- The dashboard for NeatLogs starts receiving spans at this point.
  Verify by triggering a request and checking the NeatLogs dashboard
  for a new trace within ~10 seconds.

## When to skip step 4

If step 1 classified you as **Path B (native Langfuse SDK)** — the
project calls `from langfuse import Langfuse` and uses `lf.update_...`
— step 4 alone is not enough. The native SDK does not use OTel, so
re-pointing `OTEL_EXPORTER_OTLP_ENDPOINT` does not change where the
Langfuse spans go (they go to Langfuse's hosted collector via the
SDK's own HTTP client, not via OTel).

In that case, do step 5 to replace the native SDK call sites. You
can still ALSO do step 4 if the project has OTel-routed spans from
some other instrumentation layer.

## Verify BEFORE moving to step 5 (or step 6)

1. Trigger a request; verify a new trace appears in the NeatLogs
   dashboard within 10 seconds. (Use a simple GET or run a known
   test case.)
2. Confirm the trace has the right shape: spans nested, tool calls
   recorded, prompts visible. If a span is missing, the OTel
   instrumentation might be filtered — check `OTEL_PYTHON_LOG_CORRELATION`
   and your framework's tracer config.
3. Path A is now done; you can SKIP step 5 and go to step 6.
