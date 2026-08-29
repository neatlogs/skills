# Step 2: Set up side-by-side mode

## Why

The migration must not break the existing observability. The user
is running OpenLLMetry today; turning it off before NeatLogs is
confirmed working loses visibility on the migration itself. Run
both backends in parallel for at least one full request cycle,
compare what each shows, then cut over (step 6).

## What "side-by-side" means

Both OpenLLMetry and NeatLogs receive a copy of every span. The
mechanics depend on your path (Path A or Path B from step 1).

### Path A (auto-instrumentation) — recommended side-by-side

Path A already uses the OTel SDK. Side-by-side is achieved by
**adding a second OTLP exporter** to the OTel pipeline: one for
the current collector, one for NeatLogs. The OTel SDK supports
this via `BatchSpanProcessor` chained with a second
`OTLPSpanExporter`:

```python
# In the entry module, after your existing OpenLLMetry setup:
import os
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# Existing OpenLLMetry exporter stays as-is.
# ADD a second exporter for NeatLogs:
neatlogs_exporter = OTLPSpanExporter(
    endpoint=os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"],  # set in step 3
)
trace.get_tracer_provider().add_span_processor(
    BatchSpanProcessor(neatlogs_exporter)
)
```

Important: the second exporter does not replace the first. The
existing OpenLLMetry exporter still runs. Both get every span.

### Path B (manual `tracer.start_as_current_span`) — side-by-side is harder

Path B uses the OTel SDK directly. Side-by-side works the same
way: a second exporter on the same tracer provider. The work in
step 5 is the manual span rewrite, not the side-by-side itself.

This is one reason step 5 (decorator mapping) is more involved
than step 4. The migration touches code, not just env vars.

## Rule: side-by-side runs until step 6

Until step 6 says "cut over", both backends receive every span.
The OpenLLMetry env vars and (if Path B) the manual `tracer.*`
call sites stay installed and active.

## OpenLLMetry-specific gotcha

`opentelemetry-instrumentation-*` packages install a global
`TracerProvider` when their modules are imported. The order
matters: if you import `opentelemetry.instrumentation.openai`
BEFORE `neatlogs.init(...)`, the auto-instrumentation is wired
up under the default global TracerProvider, which by default
uses `ConsoleSpanExporter` (no-op). To route auto-instrumented
spans to NeatLogs, you must configure the OTel SDK's
`TracerProvider` (with `BatchSpanProcessor` + `OTLPSpanExporter`)
BEFORE the auto-instrumentation modules are imported. This is
the same import-order issue documented in `neatlogs-py` step 2;
the migration respects it.

## Verify BEFORE moving to step 3

1. The second OTel exporter is added and running (Path A), or
   you've identified the specific manual call sites that need
   explicit NeatLogs spans in addition to OpenLLMetry (Path B).
2. The project still boots and serves traffic. The side-by-side
   change is additive, not a cutover.
3. The OTel `TracerProvider` is configured (with the
   `BatchSpanProcessor` for NeatLogs) before the auto-
   instrumentation modules are imported.
