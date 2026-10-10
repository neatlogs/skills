---
name: neatlogs-public-api-cli
description: Use when reading NeatLogs traces or managing a cloud project through the supported Public API or neatlogs-cli. Covers project-scoped authentication, CLI commands, safe trace readback, pagination, and the boundary between SDK ingest and public reads.
---

# NeatLogs Public API and CLI

Use this skill for **cloud project reads and management**. For instrumenting an
application or sending telemetry, use the Python, TypeScript, Go, or direct
ingest skill instead. The SDK ingest credential and endpoint are separate from
the Public API host and its authorization rules.

This guidance targets **neatlogs-cli 0.2.1**, pending npm publication. Check the registry before installing it; do not claim a successful upgrade when that version is unavailable. The 0.2.0 compatibility path is in [authentication and operation selection](references/auth-and-operations.md).

This guidance follows `neatlogs/neatlogs-app` `staging` at
`8599c674ae103f39f98ace928f37bb553b877b01`. Before relying on a newly
deployed capability, inspect the installed CLI's offline `schema show` output
and confirm the target deployment enables the operation. A schema entry does
not prove that a gated operation is enabled on the server.

## Choose the supported client

- The Public API is under `/api/v1/public/*` on the **dashboard/app origin**,
  such as `https://app.neatlogs.com`, `https://dev.neatlogs.com`,
  `https://staging.neatlogs.com`, or `https://eu.app.neatlogs.com`. Use the
  deployment that owns the project. Do not send Public API reads to an SDK
  ingest host or the dashboard's internal `/api/traces/v3/*` route.
- The standalone npm package is `neatlogs-cli`; its executable is `neatlogs`.
  It is distinct from the TypeScript SDK package `neatlogs`, which also has a
  `neatlogs` executable for SDK Doctor. Check which package supplies the local
  executable before running a command.
- The supported trace command is `neatlogs traces get <trace-id>`. The CLI also
  provides `neatlogs traces spans list <trace-id>`. Do not substitute the SDK
  PR's proposed `neatlogs trace get` command.
- Public API and CLI support is limited to the approved cloud origins and the
  explicitly enabled localhost development profile. Do not infer self-hosted
  Public API support from an SDK that can export to a custom endpoint.

Read [authentication and operation selection](references/auth-and-operations.md)
before configuring a profile, token, or direct HTTP request. Read
[trace readback](references/trace-readback.md) before checking a real trace.

## Read a trace through the CLI

For a human, use Node.js 22 or 24 and verify which CLI is installed. Choose a
profile for the project's dashboard. Inspect existing profiles before login;
reuse a name only if it is unused or already bound to that exact host. For EU,
change both the host and profile below to `https://eu.app.neatlogs.com` and
`neatlogs-eu`. Do not rebind an authenticated profile from another dashboard.

```bash
npm view neatlogs-cli@0.2.1 version
npm install --global neatlogs-cli@0.2.1
neatlogs --version
NEATLOGS_CLI_HOST='https://app.neatlogs.com'
NEATLOGS_CLI_PROFILE='neatlogs-us'
neatlogs --host "$NEATLOGS_CLI_HOST" profile list
neatlogs --host "$NEATLOGS_CLI_HOST" --profile "$NEATLOGS_CLI_PROFILE" \
  --credential-source profile auth login --device \
  --scope context:read observability:read offline_access
# Continue after the user approves the displayed code in their browser.
env -u NEATLOGS_PROJECT_ID neatlogs --host "$NEATLOGS_CLI_HOST" \
  --profile "$NEATLOGS_CLI_PROFILE" --credential-source profile projects list
NEATLOGS_CLI_PROJECT='<project-uuid>'
neatlogs --host "$NEATLOGS_CLI_HOST" --profile "$NEATLOGS_CLI_PROFILE" \
  --credential-source profile --project "$NEATLOGS_CLI_PROJECT" whoami --json
neatlogs --host "$NEATLOGS_CLI_HOST" --profile "$NEATLOGS_CLI_PROFILE" \
  --credential-source profile --project "$NEATLOGS_CLI_PROJECT" traces list --limit 5 --json
neatlogs --host "$NEATLOGS_CLI_HOST" --profile "$NEATLOGS_CLI_PROFILE" \
  --credential-source profile --project "$NEATLOGS_CLI_PROJECT" traces get '<trace-id>' --json
neatlogs --host "$NEATLOGS_CLI_HOST" --profile "$NEATLOGS_CLI_PROFILE" \
  --credential-source profile --project "$NEATLOGS_CLI_PROJECT" traces spans list '<trace-id>' --limit 50 --json
```

`projects list` must receive neither `--project` nor `NEATLOGS_PROJECT_ID`;
`env -u` excludes the variable only from that process on POSIX shells. Use
equivalent process isolation in other shells. Confirm the project UUID from
discovery before project-scoped `whoami` and trace reads. Keep the same host,
profile and credential source for subsequent reads, including pagination.

For unattended agents and CI, use an expiring service-account token from a
secret store in `NEATLOGS_TOKEN`, with the minimum project binding,
`context:read` for discovery/identity, and `observability:read` for traces.
Use `--credential-source token` instead of `profile`, skip human OAuth login,
and keep the explicit host and project selection. The SDK project's
`NEATLOGS_API_KEY` stays available to the application and does not override
either explicit credential source. Do not put tokens in command arguments,
chat, repository files, or output.

With only an SDK project key, use the installed same-language SDK's documented
`doctor --local` and `doctor --probe` for controlled capture and hosted
readback. These are SDK commands, not commands of `neatlogs-cli`. Mark optional
CLI readback **waiting on a human** until OAuth approval or a suitable service
token is available. A probe pass is separate from verifying the application's
actual trace; ask for dashboard verification if public-read credentials are
unavailable.

In 0.2.1, `auth status` verifies with the public API and needs `context:read`
but no selected project. In 0.2.0 it can report `authenticated: true` merely
because an SDK key is present. Use project-scoped `whoami` and an actual trace
read to verify access. See the authentication reference for recovery from
`MISSING_HOST`, `MISSING_PROJECT_ID`, credential failures and host mismatches.

`traces get` returns safe trace metadata. It does **not** return the full span
tree. Follow `data.page.nextCursor` across `traces spans list` pages if the
task requires all spans. Treat incomplete pagination as incomplete evidence.
Confirm the exact trace ID and project, a finalized status, expected span
types and parent links, and the user's requested behavior. Zero token usage
alone is not a regression: some providers do not report token counts.

The Public API or CLI is suitable for checking the **finalized trace visible to
users** after instrumentation, including its canonical root and parent
hierarchy once pagination is complete.

"All spans," root, and parent checks here cover the **canonical finalized
public projection**, not the originally emitted span topology. Finalization
can repair parent links and attach extra roots beneath one root, so a single
root in a complete public read does not prove that only one root was emitted.
If the task requires proof of emitted root or parent structure, use a
separately authorized raw-span read; if that is unavailable, report the emitted
topology as unverified. Routine safe metadata reads do not require raw or
payload access.

When a trace is pending, retry a bounded number of times. A dead-lettered
trace requires investigation; do not describe it as simply waiting for a
flush. Report missing access or an unavailable API as a blocker rather than
claiming successful readback.

## Other operations

Use `neatlogs --help`, `neatlogs schema list`, `neatlogs schema search <query>`,
and `neatlogs schema show <operationId>` to discover the installed CLI's
release-embedded contract. `schema` commands are offline. Curated commands
cover projects, traces, sessions, detections, evaluations, analytics, prompts,
skills, and other authorized resources; choose the exact operation and minimum
scope for the user's task. Request or perform mutations only when the user
authorized them and the target deployment permits them.

Backend contract: [Public API v1](https://github.com/neatlogs/neatlogs-app/blob/8599c674ae103f39f98ace928f37bb553b877b01/backend/docs/public-api/v1.md).
CLI source: [command reference](https://github.com/neatlogs/neatlogs-app/blob/8599c674ae103f39f98ace928f37bb553b877b01/cli/docs/command-reference.md).
