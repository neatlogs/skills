# HTTP ingest (`POST /v1/trace`)

Use this dependency-free path by default when the application's language is not supported by a Neatlogs SDK.

Send one nested JSON trace to the host for the project's region. For other managed projects:

```text
POST https://ingest.neatlogs.com/v1/trace
```

Select the ingest host for the project's region before running the example:

```bash
# EU project
export NEATLOGS_INGEST_URL=https://eu.ingest.neatlogs.com
```

```bash
# Other managed project
export NEATLOGS_INGEST_URL=https://ingest.neatlogs.com
```

Authenticate with a Neatlogs write key in either `x-api-key` or `Authorization: Bearer ...`. When using a write key, include the target project name in the root-level `project` field.

```bash
curl -X POST "$NEATLOGS_INGEST_URL/v1/trace" \
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
