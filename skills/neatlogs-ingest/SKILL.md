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
- This skill does not grant platform access. The marker-aware `get_trace_context` contract must be deployed on the hosted Neatlogs backend; a merged backend change or updated local wizard alone is not proof.
- For the representative submission, generate a UUID and append `neatlogs.verification.marker=<UUID>` to `OTEL_RESOURCE_ATTRIBUTES`, preserving existing entries and scoping it only to the launched process. Do not edit source or persistent configuration, and do not treat the marker as a secret. For direct HTTP ingest, also include this canonical resource attribute in the uncommitted representative payload. Immediately before the real-path submission, record the current UTC timestamp. If the coding agent cannot launch a web UI path, tell the user exactly how to start the app with that temporary environment value, then continue verification against the same marker.
- After submission, call the already-connected Neatlogs platform MCP's existing `get_trace_context(verification_marker=<same UUID>)` directly; make no preliminary MCP discovery calls and never fall back to the latest trace if the marker is absent; report that exact blocker and leave verification incomplete. While `status` is `processing` or `finalization_status` is `pending`, poll the same trace with `get_trace_context(trace_id=<trace_id>)`. Only after `finalization_status` is `finalized`, page with `get_trace_context(trace_id=<trace_id>, offset=<next_offset>)` until `next_offset` is null, and verify that all `span_count` spans were inspected.
- If `get_trace_context` rejects `verification_marker`, `trace_id`, or `offset`, or omits `status`, `finalization_status`, `next_offset`, or `span_count`, treat the hosted MCP as an old contract: stop, report the hosted deployment blocker, and do not claim verification or use another trace query.
- If no Neatlogs platform MCP is connected, ask the user to configure `https://ingest.neatlogs.com/mcp` (or `npx @neatlogs/wizard mcp --api-key <PROJECT_KEY>`) in the coding agent, storing the project key as a client secret. Never print or request the key in chat. Leave verification incomplete until platform evidence is available.
- Inspect the full persisted span tree and attributes. Confirm the marker-matched project trace is the fresh submission; a trace-list summary, local serialization check, or successful HTTP connection alone is insufficient.
- If build, restart, exercise, or live platform confirmation cannot be completed, state the exact blocker and leave setup explicitly incomplete.
