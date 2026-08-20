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
- This skill does not grant platform access. The marker-aware `get_trace_context` contract must be deployed on the hosted Neatlogs backend, and the installed SDK or exporter must preserve the resource marker; merged source changes or an updated local wizard alone are not proof.
- For the representative submission, generate two distinct UUIDs: a marker and an exercise nonce. With OTLP, append `neatlogs.verification.marker=<marker UUID>` to `OTEL_RESOURCE_ATTRIBUTES`, preserving existing entries and scoping it only to the launched process. Put the exact token `neatlogs-verification:<nonce UUID>` in a safe application input that should be captured as a persisted span `input_value`. With direct HTTP ingest, put the marker under the uncommitted representative root payload's `attributes` and the nonce token in a representative root or child `input`; this makes both values trace-specific. Do not edit source or persistent configuration, and do not treat either value as a secret. Immediately before submission, record the current UTC timestamp. If the path cannot safely carry a unique captured input, report that blocker and leave verification incomplete.
- After the OTLP exercise finishes, flush telemetry and gracefully stop the marked process or relaunch it without the marker before discovery; if marked trace production cannot be quiesced, leave verification incomplete. Direct HTTP submission needs no process quiescence. Call the already-connected Neatlogs platform MCP with `get_trace_context(verification_marker=<marker UUID>, candidate_offset=0)`. Enumerate offsets from 0 upward, collecting distinct trace IDs until MCP returns `No project trace found` for the next offset. For every candidate, page its complete span set with `get_trace_context(trace_id=<trace_id>, offset=<next_offset>)` until `next_offset` is null. A candidate qualifies only when the exact nonce token appears in a persisted span `input_value`, its top-level `name` and `workflow` plus parentless root span match the submitted path, its `created_at` is not earlier than the recorded timestamp, `root_span_count` is 1, and no span has `synthetic_recovery_root: true`. Never select the first or latest marker match. If no trace qualifies yet, poll every 5 seconds and repeat the full enumeration for up to 2 minutes. Restart a scan if offsets shift and duplicate a trace ID; if a complete distinct scan cannot be obtained, offset 100 still returns a candidate, or zero or multiple traces qualify, report the ambiguity and leave verification incomplete.
- Once exactly one trace qualifies, poll that exact `trace_id` every 5 seconds for up to 2 minutes while `status` is `processing` or `finalization_status` is `pending`. If it does not reach `finalized` within that bound, leave verification incomplete. Treat a null or unrecognized `finalization_status` as a hosted-contract blocker. After `finalization_status` is `finalized`, require `trace_context_contract_version: 2`, `verification_ready: true`, `span_payload_complete: true`, `span_tree_complete: true`, and `root_span_count: 1`; otherwise report a hosted-contract or incomplete-payload blocker. Page all spans again and perform two identical full marker-candidate enumerations at least 10 seconds apart to confirm that exactly one trace contains the nonce in both scans. Verify that all `span_count` spans were inspected.
- If `get_trace_context` rejects `verification_marker`, `candidate_offset`, `trace_id`, or `offset`, or omits `trace_context_contract_version`, `verification_ready`, `span_payload_complete`, `span_tree_complete`, `root_span_count`, `trace_id`, `name`, `workflow`, `created_at`, `spans[].parent_span_id`, `spans[].input_value`, `status`, `finalization_status`, `next_offset`, or `span_count`, treat the hosted MCP as an old contract: stop, report the hosted deployment blocker, and do not claim verification or use another trace query.
- If no Neatlogs platform MCP is connected, ask the user to configure `https://ingest.neatlogs.com/mcp` (or `npx @neatlogs/wizard mcp --api-key <PROJECT_KEY>`) in the coding agent, storing the project key as a client secret. Never print or request the key in chat. Leave verification incomplete until platform evidence is available.
- Inspect the full persisted span tree and returned semantic fields. Confirm the nonce-qualified project trace is the fresh submission; a trace-list summary, local serialization check, or successful HTTP connection alone is insufficient.
- If build, restart, exercise, or live platform confirmation cannot be completed, state the exact blocker and leave setup explicitly incomplete.
