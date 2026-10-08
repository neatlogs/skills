# Public API authentication and operation selection

Source: `neatlogs/neatlogs-app` `staging` commit
`7253b22987c749cb4b1b50c063f6903c313273d3`, especially
[`backend/docs/public-api/v1.md`](https://github.com/neatlogs/neatlogs-app/blob/7253b22987c749cb4b1b50c063f6903c313273d3/backend/docs/public-api/v1.md),
[`cli/src/config.ts`](https://github.com/neatlogs/neatlogs-app/blob/7253b22987c749cb4b1b50c063f6903c313273d3/cli/src/config.ts), and
[`cli/README.md`](https://github.com/neatlogs/neatlogs-app/blob/7253b22987c749cb4b1b50c063f6903c313273d3/cli/README.md).

## Host and credential

| Caller | Credential | Selection |
| --- | --- | --- |
| Human | CLI browser OAuth, or explicit Device Flow | App-origin profile and an accessible selected project |
| Agent or CI | Expiring `nlsa_` service-account token with minimum scope | `NEATLOGS_HOST`, `NEATLOGS_PROJECT_ID`, `NEATLOGS_TOKEN` |
| Existing Public API integration | Project-bound legacy `nlpk_` public API key where permitted | Public API's legacy key carrier and its bound project |
| Application exporting telemetry | SDK ingest credential | SDK ingest endpoint, not a replacement for public-read authorization |

The CLI accepts `NEATLOGS_API_KEY` as a **legacy public API credential** fallback.
Do not assume that the application's SDK ingest key grants Public API read
access. `NEATLOGS_TOKEN` and `NEATLOGS_API_KEY`, if both set, must match; the
CLI rejects conflicting credentials. Service-account and OAuth tokens use the
Bearer carrier. The legacy public API key may use `x-api-key` or Bearer. A
service-account token is not accepted as an `x-api-key` value.

The Public API host is the app origin. It is not `ingest.neatlogs.com`,
`eu.ingest.neatlogs.com`, or a private backend origin. OAuth tokens are bound
to their issuer and resource; set up separate profiles for regions. Use only
the approved cloud origins or the explicitly enabled localhost profile.

For a direct HTTP read, the operation is
`GET /api/v1/public/traces/{traceId}` on the app origin. A service-account
request has `Authorization: Bearer <token>` and
`x-project-id: <project-uuid>` headers. Keep the token in a secret store and
avoid logging its value. Successful responses have `success: true`,
`requestId`, and `data`; errors use the Public API problem response. Never
parse the dashboard's internal trace response as though it were this envelope.

## Choose and verify an operation

The CLI contains a release-embedded OpenAPI contract:

```bash
neatlogs schema list
neatlogs schema search traces
neatlogs schema show get_api_v1_public_traces_traceId
```

The offline schema can expose operations behind a runtime gate. Inspect the
operation's gate, authentication, scopes, request/response schema, and risk
metadata, then confirm the target deployment actually enables it. Prefer a
curated CLI command when available; use `neatlogs api <operationId>` only when
the operation's contract requires it. For agent and CI reads, bind only the
needed projects and use `observability:read` for trace metadata and spans.

Use the installed CLI's help for exact option syntax. `--json` is a global
output option. `traces list` supports a bounded `--all --max-items` mode;
`traces spans list` uses explicit `--cursor` pagination. Never collect an
unbounded list by repeatedly following cursors without a task-specific
ceiling.
