# Step 2: Set up side-by-side mode

## Why

The migration must not break the existing observability. The user
is running LangSmith today; turning it off before NeatLogs is
confirmed working loses visibility on the migration itself. Run
both backends in parallel for at least one full request cycle,
compare what each shows, then cut over (step 6).

## What "side-by-side" actually means

Both LangSmith and NeatLogs receive a copy of every span. The
mechanics depend on your path (Path A or Path B from step 1).

### Path A (LangChain auto-tracing via OTel) — recommended side-by-side

Path A uses the OTel SDK. Side-by-side is achieved by **adding a
second OTLP exporter** to the OTel pipeline: one for LangSmith,
one for NeatLogs. The OTel SDK supports this via
`BatchSpanProcessor` chained with a second `OTLPSpanExporter`:

```python
# In the entry module, after your existing LangChain/LangSmith setup:
import os
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# Existing LangSmith/LangChain exporter stays as-is.
# ADD a second exporter for NeatLogs:
neatlogs_exporter = OTLPSpanExporter(
    endpoint=os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"],  # set in step 3
)
trace.get_tracer_provider().add_span_processor(
    BatchSpanProcessor(neatlogs_exporter)
)
```

Important: **the second exporter does NOT replace the first**. The
LangSmith/LangChain exporter still runs. Both get every span.

### Path B (explicit `@traceable` SDK) — side-by-side is harder

Path B uses `from langsmith import traceable` and the
`langsmith_client` directly. The SDK does not use OTel under the
hood for the trace tree itself. To get side-by-side in this case
you have to add a parallel OTel layer (or use NeatLogs explicitly
via `neatlogs.span(...)` and `neatlogs.wrap(...)` for the modules
LangSmith touches).

This is one reason step 5 (decorator mapping) is more involved
than step 4 — the migration touches code, not just env vars.

## Rule: side-by-side runs UNTIL step 6

Until step 6 says "cut over", BOTH backends receive every span.
The LangSmith env vars and (if Path B) the LangSmith SDK call
sites stay installed and active.

## LangChain-specific gotcha

If the project uses LangChain's `langchain.observability` callback
(v0.3+), the callback is registered globally. Adding a second
exporter is straightforward, but verify that the `langchain.observability`
v2 tracer is still wired to the LangSmith endpoint (it is, by
default — that's what makes side-by-side work). If you've already
re-pointed the OTel exporter to NeatLogs in step 4, the
`langchain.observability` tracer will now send LangChain spans to
NeatLogs. That's the side-by-side mode.

## Verify BEFORE moving to step 3

1. The second OTel exporter is added and running (Path A), OR
   you've identified the specific call sites that need explicit
   NeatLogs spans in addition to LangSmith (Path B).
2. The project still boots and serves traffic — the side-by-side
   change is additive, not a cutover.
3. The `langchain.observability` tracer (if used) is still wired
   to the LangSmith endpoint, not yet to NeatLogs.
