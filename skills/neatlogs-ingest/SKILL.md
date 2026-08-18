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

## Live completion gate (wizard or standalone coding agent)

- Show concise, secret-free progress for transport selection, edits/configuration, validation/build, process restart, real-path exercise, and platform confirmation.
- Run the project's existing checks and validate the outgoing payload/OTel configuration. Restart the application or Collector that loads the changed exporter settings.
- Exercise the actual application behavior that should emit telemetry. With direct HTTP ingest, that behavior must submit one representative nested `/v1/trace` payload. With OTLP, it must create spans in the application and let the configured SDK exporter and, when present, Collector deliver them; do not replace this with a synthetic connectivity probe.
- This skill does not grant platform access. Immediately before the real-path submission, record the current UTC timestamp. After submission, call the already-connected Neatlogs platform MCP's existing `get_trace_context(created_after=<UTC timestamp>)` directly to select the latest trace in the intended project; make no preliminary MCP discovery calls. While `status` is `processing` or `finalization_status` is `pending`, poll that same trace with `get_trace_context(trace_id=<trace_id>)`. Once finalized, page with `get_trace_context(trace_id=<trace_id>, offset=<next_offset>)` until `next_offset` is null, and verify that all `span_count` spans were inspected.
- If no Neatlogs platform MCP is connected, ask the user to configure `https://ingest.neatlogs.com/mcp` (or `npx @neatlogs/wizard mcp --api-key <PROJECT_KEY>`) in the coding agent, storing the project key as a client secret. Never print or request the key in chat. Leave verification incomplete until platform evidence is available.
- Inspect the full persisted span tree and attributes. Confirm the latest project trace is the fresh submission; a trace-list summary, local serialization check, or successful HTTP connection alone is insufficient.
- If build, restart, exercise, or live platform confirmation cannot be completed, state the exact blocker and leave setup explicitly incomplete.
