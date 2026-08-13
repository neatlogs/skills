# HTTP ingest (`POST /v1/trace`)

Use this dependency-free path by default when the application's language is not supported by a Neatlogs SDK.

Send one nested JSON trace to:

```text
POST https://ingest.neatlogs.com/v1/trace
```

Authenticate with a Neatlogs write key in either `x-api-key` or `Authorization: Bearer ...`. When using a write key, include the target project name in the root-level `project` field.

```bash
curl -X POST https://ingest.neatlogs.com/v1/trace \
  -H "Content-Type: application/json" \
  -H "x-api-key: $NEATLOGS_WRITE_KEY" \
  -d '{
    "name": "answer-question",
    "project": "my-project",
    "children": [
      {
        "name": "retrieve-context",
        "kind": "RETRIEVER",
        "query": "What is HTTP ingest?",
        "documents": [{"id": "doc-1", "content": "Use POST /v1/trace."}]
      },
      {
        "name": "generate-answer",
        "kind": "LLM",
        "model": "my-model",
        "input": "What is HTTP ingest?",
        "output": "POST one nested JSON trace to /v1/trace."
      }
    ]
  }'
```

The root object is the `WORKFLOW` span. Nest spans under `children`; do not manufacture `trace_id`, `span_id`, or `parent_span_id`. Useful fields on every node include `name`, `kind`, `input`, `output`, `query`, `documents`, `model`, `tokens`, `status`, `error`, `duration_ms`, `metadata`, `attributes`, `logs`, and `children`.

Use canonical direct attributes under `attributes`, including `neatlogs.retriever.*`. Do not send simple JSON to `/v1/traces`; that plural endpoint expects OTLP protobuf.
