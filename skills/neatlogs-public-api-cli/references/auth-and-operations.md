# Public API authentication and operation selection

Source: `neatlogs/neatlogs-app` `staging` commit
`8599c674ae103f39f98ace928f37bb553b877b01`, especially
[`backend/docs/public-api/v1.md`](https://github.com/neatlogs/neatlogs-app/blob/8599c674ae103f39f98ace928f37bb553b877b01/backend/docs/public-api/v1.md),
[`cli/src/config.ts`](https://github.com/neatlogs/neatlogs-app/blob/8599c674ae103f39f98ace928f37bb553b877b01/cli/src/config.ts), and
[`cli/README.md`](https://github.com/neatlogs/neatlogs-app/blob/8599c674ae103f39f98ace928f37bb553b877b01/cli/README.md).

## Host and credential

| Caller | Credential | Selection |
| --- | --- | --- |
| Human | CLI browser OAuth, or explicit Device Flow | App-origin profile and an accessible selected project |
| Agent or CI | Expiring `nlsa_` service-account token with minimum scope | `NEATLOGS_HOST`, `NEATLOGS_PROJECT_ID`, `NEATLOGS_TOKEN` |
| Existing Public API integration | Project-bound legacy `nlpk_` public API key where permitted | Public API's legacy key carrier and its bound project |
| Application exporting telemetry | SDK ingest credential | SDK ingest endpoint, not a replacement for public-read authorization |

The CLI accepts `NEATLOGS_API_KEY` as a **legacy public API credential** fallback.
Do not assume that the application's SDK ingest key grants Public API read
access. In 0.2.1, choose `--credential-source profile` for stored OAuth or
`--credential-source token` for `NEATLOGS_TOKEN` only. Both explicit sources
ignore the application's SDK key. The default `auto` mode prefers environment
credentials over OAuth: `NEATLOGS_TOKEN` and `NEATLOGS_API_KEY`, if both set,
must match or the CLI rejects them. Service-account and OAuth tokens use the
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

## Version compatibility and authentication recovery

The target release is 0.2.1, pending publication. Confirm `neatlogs --version`
and `neatlogs --help` before using `--credential-source`. Published 0.2.0 lacks
this option. For 0.2.0, omit the option and prefix **every** OAuth command with
`env -u NEATLOGS_API_KEY -u NEATLOGS_TOKEN` on POSIX; for service-token commands,
exclude only `NEATLOGS_API_KEY`. Other shells need equivalent per-process
environment isolation. Do not unset the application's SDK key globally.

- `MISSING_HOST`: pass the regional dashboard origin with `--host` on login
  and reads. Do not assume a cloud-host default or use an ingest host.
- `MISSING_PROJECT_ID`: list accessible projects first without `--project`
  or `NEATLOGS_PROJECT_ID`, then pass the chosen UUID for `whoami` and trace
  reads. A saved profile's project is omitted automatically for discovery.
- `UNAUTHORIZED` / 401 with an SDK key: public reads need OAuth or a suitable
  service token; repeating the SDK key will not fix authorization. With only
  that key, use SDK Doctor readback and mark CLI readback waiting on a human.
- Profile/host mismatch: choose an existing profile for that exact host or a
  new unused name, log in there, and use it consistently. Do not change the
  host of an authenticated profile to reuse its credentials elsewhere.
- `auth status`: 0.2.0 reports local credential presence, which is not proof
  of public API acceptance. In 0.2.1 it verifies online with `context:read`,
  without project selection. An authentication rejection reports
  `authenticated: false`; network/server/scope failures remain errors.
  Successful status does not establish permission to every project or trace.
- `NOT_FOUND` from `traces get`: confirm the trace ID and project. The command
  is plural `traces get`; use `traces spans list` for individual spans.

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
