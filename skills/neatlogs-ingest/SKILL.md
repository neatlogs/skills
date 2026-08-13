---
name: neatlogs-ingest
description: Use when sending traces to Neatlogs from a language without a supported Neatlogs SDK, or when configuring direct HTTP ingest, OTLP/gRPC, an OpenTelemetry exporter, or an OpenTelemetry Collector. Defaults unsupported languages to POST /v1/trace nested JSON and documents the separate OTLP transports.
---

# Neatlogs direct ingest

Choose the transport before changing code:

1. For Python, TypeScript/Node.js, or Go, use the corresponding Neatlogs SDK skill unless the user explicitly requests a direct transport.
2. For any other language, default to the dependency-free HTTP ingest endpoint `POST https://ingest.neatlogs.com/v1/trace`. Read [`references/http-ingest.md`](references/http-ingest.md).
3. If the application already emits OpenTelemetry spans or uses an OpenTelemetry Collector, it may send OTLP over gRPC instead. Read [`references/grpc-ingest.md`](references/grpc-ingest.md).

Keep the endpoints distinct:

| Name | Endpoint | Payload |
|---|---|---|
| HTTP ingest | `POST /v1/trace` | One nested JSON trace; Neatlogs generates IDs |
| OTLP/HTTP | `POST /v1/traces` | OTLP protobuf from an OpenTelemetry exporter |
| OTLP/gRPC | `ingest.neatlogs.com:443` | OTLP `TraceService/Export` |

Never send the nested HTTP-ingest JSON body to `/v1/traces`.

For retrieval attributes set directly by the caller, emit `neatlogs.retriever.*`. OpenTelemetry-native sources may emit `gen_ai.retrieval.*`; Neatlogs maps those during ingestion. Do not emit the legacy `neatlogs.retrieval.*` namespace from new integrations.
