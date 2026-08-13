# OTLP/gRPC ingest

Use OTLP/gRPC when an unsupported-language application already has OpenTelemetry instrumentation, or when an OpenTelemetry Collector is available. For an unsupported language with no OpenTelemetry setup, prefer the simpler HTTP ingest endpoint `POST /v1/trace`.

Configure a standard OTLP trace exporter with:

```text
Endpoint: ingest.neatlogs.com:443
TLS: enabled
Metadata: x-api-key=<Neatlogs project key>
Service: opentelemetry.proto.collector.trace.v1.TraceService/Export
```

Do not put the project key in `Authorization: Bearer ...` for gRPC; use `x-api-key` metadata.

Standard OpenTelemetry environment variables:

```bash
export OTEL_EXPORTER_OTLP_TRACES_PROTOCOL=grpc
export OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=https://ingest.neatlogs.com
export OTEL_EXPORTER_OTLP_TRACES_HEADERS=x-api-key=$NEATLOGS_API_KEY
```

Register a batch span processor and flush or shut down the tracer provider before a short-lived process exits.

OpenTelemetry GenAI retrieval attributes are normalized as follows:

| OpenTelemetry | Neatlogs |
|---|---|
| `gen_ai.retrieval.query.text` | `neatlogs.retriever.query` |
| `gen_ai.retrieval.top_k` | `neatlogs.retriever.top_k` |
| `gen_ai.retrieval.documents` | `neatlogs.retriever.documents.0`, `.1`, … |

`POST /v1/traces` is the separate OTLP/HTTP protobuf endpoint. It is not the nested-JSON HTTP ingest API.
