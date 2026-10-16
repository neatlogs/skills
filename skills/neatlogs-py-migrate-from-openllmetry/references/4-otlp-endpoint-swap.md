# Step 4: OTLP-endpoint swap — the 90% path

## Why this is the easy path

If step 1 classified you as **Path A (auto-instrumentation)**
— i.e. your project uses `opentelemetry-instrumentation-*`
packages and routes spans through the OTel SDK — the entire
migration is **2 environment variables**. No code changes.

Path A covers the majority of OpenLLMetry users: anyone using
the `opentelemetry-instrumentation-openai` /
`opentelemetry-instrumentation-anthropic` / etc. meta-packages,
anyone using `opentelemetry-instrumentation` to auto-load
many instrumentors at startup, and anyone using the OTel SDK
directly with `OTLPSpanExporter` pointing at a collector.

## Action

1. Find the current OTel env vars:
   ```bash
   grep -rE 'OTEL_EXPORTER_OTLP_(ENDPOINT|HEADERS)|OTEL_SERVICE_NAME' . \
     --include='.env*' --include='*.env*' --include='*.yaml' --include='*.yml' --include='*.json' 2>/dev/null
   ```
2. Update them to point at NeatLogs.

   **Before (any OTel collector):**
   ```bash
   OTEL_EXPORTER_OTLP_ENDPOINT=https://your-collector.example.com
   OTEL_EXPORTER_OTLP_HEADERS=Authorization=Bearer%20${COLLECTOR_TOKEN}
   OTEL_SERVICE_NAME=my-app
   ```
   (The actual values vary — Phoenix, Tempo, Honeycomb, Jaeger,
   Datadog, etc. all use the OTel SDK; the migration is the same
   shape regardless.)

   **After (NeatLogs):**
   ```bash
   OTEL_EXPORTER_OTLP_ENDPOINT=https://ingest.neatlogs.com
   OTEL_EXPORTER_OTLP_HEADERS=x-api-key=${NEATLOGS_API_KEY}
   ```
   Notes:
   - The NeatLogs endpoint is `/v1/traces` — the OTel SDK
     appends the path itself when you set the endpoint without
     a path. Some OTel versions require an explicit path; if
     you see 404s, set
     `OTEL_EXPORTER_OTLP_ENDPOINT=https://ingest.neatlogs.com/v1/traces`
     directly.
   - The auth header is `x-api-key: <value>`, NOT
     `Authorization: Bearer`.
   - URL-encode the `=` and `:` in the value when using a
     header dict string; the OTel SDK also accepts a
     comma-separated `k1=v1,k2=v2` form.
3. **Set `OTEL_SERVICE_NAME` to your `workflow_name`** if it
   was already in use. The service name shows up in NeatLogs
   as the Workflow column.
4. If you have a `requirements.txt` / `pyproject.toml` that
   hardcodes the collector endpoint, update it too.
5. If step 2 added a second OTel exporter for NeatLogs (the
   side-by-side pattern), REMOVE the second exporter — the
   endpoint swap now sends the same spans to NeatLogs. The
   first exporter (the one for your previous collector) stays;
   that's the side-by-side.

## What you learn

- Path A is now done. Traces flow into both your previous
  collector and NeatLogs.
- The dashboard for NeatLogs starts receiving spans at this
  point. Verify by triggering a request and checking the
  NeatLogs dashboard for a new trace within ~10 seconds.

## When to skip step 4

If step 1 classified you as **Path B (manual
`tracer.start_as_current_span`)** — the project calls
`trace.get_tracer(__name__)` and uses `with
tracer.start_as_current_span("name", ...)` directly — step 4
alone is not enough. The manual spans go through the OTel SDK
so the endpoint swap does help, but if the project has its own
`BatchSpanProcessor` chain you may have to also update that.

In that case, do step 5 to replace the manual call sites. You
can still ALSO do step 4 if the project has OTel-routed spans
from some other instrumentation layer.

## Auto-instrumentation caveat

Even after step 4, if the auto-instrumentation modules
(`opentelemetry.instrumentation.openai`, etc.) are still
imported, they continue to create spans through the OTel
SDK. The OTel SDK now sends those spans to NeatLogs (via the
endpoint swap). This is the side-by-side mode. Step 6
(cutover) is what removes the auto-instrumentation modules
(or redirects them elsewhere).

## OpenInference semantic attributes caveat

OpenLLMetry adds OpenInference semantic attributes
(`openinference.span.kind`, `openinference.*`) to spans by
default. NeatLogs receives these as plain attributes; the
dashboard renders them as part of the span's metadata. If
you want the OpenInference `span_kind` to drive NeatLogs'
`kind` for grouping/analytics, run the OpenInference span
through a `SpanProcessor` that reads `openinference.span.kind`
and rewrites it to `neatlogs.kind`. The simpler path: drop
the OpenInference attributes (the `tracer` doesn't add them
unless you call `set_attribute` yourself) and let NeatLogs
add its own `kind` via `@neatlogs.span(kind=...)` decorators
in step 5.

## Verify BEFORE moving to step 5 (or step 6)

1. Trigger a request; verify a new trace appears in the
   NeatLogs dashboard within 10 seconds.
2. Confirm the trace has the right shape: spans nested, tool
   calls recorded, prompts visible. If a span is missing, the
   OTel instrumentation might be filtered — check
   `OTEL_PYTHON_LOG_CORRELATION` and your auto-instrumentation
   library's tracer config.
3. Path A is now done; you can SKIP step 5 and go to step 6.
