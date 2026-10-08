---
name: neatlogs-public-api-cli
description: Use when reading NeatLogs traces or managing a cloud project through the supported Public API or neatlogs-cli. Covers project-scoped authentication, CLI commands, safe trace readback, pagination, and the boundary between SDK ingest and public reads.
---

# NeatLogs Public API and CLI

Use this skill for **cloud project reads and management**. For instrumenting an
application or sending telemetry, use the Python, TypeScript, Go, or direct
ingest skill instead. The SDK ingest credential and endpoint are separate from
the Public API host and its authorization rules.

This guidance follows `neatlogs/neatlogs-app` `staging` at
`7253b22987c749cb4b1b50c063f6903c313273d3`. Before relying on a newly
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

For a human, use Node.js 22 or 24, install the published standalone CLI,
verify `neatlogs --version`, then configure an app-origin profile and log in:

```bash
npm install --global neatlogs-cli@latest
neatlogs --version
neatlogs profile set work --host https://app.neatlogs.com --project <project-uuid>
neatlogs profile use work
neatlogs auth login --scope observability:read
neatlogs traces get <trace-id> --json
neatlogs traces spans list <trace-id> --limit 50 --json
```

For an unattended agent or CI job, use a dedicated service account with the
minimum project binding and `observability:read` scope. Supply its token from
a secret store as `NEATLOGS_TOKEN`, its dashboard origin as `NEATLOGS_HOST`,
and its selected project UUID as `NEATLOGS_PROJECT_ID`; do not perform a human
OAuth login in automation. Do not put credentials in command arguments, chat,
repository files, or output.

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

Backend contract: [Public API v1](https://github.com/neatlogs/neatlogs-app/blob/7253b22987c749cb4b1b50c063f6903c313273d3/backend/docs/public-api/v1.md).
CLI source: [command reference](https://github.com/neatlogs/neatlogs-app/blob/7253b22987c749cb4b1b50c063f6903c313273d3/cli/docs/command-reference.md).
