---
name: neatlogs-py-migrate-from-langsmith
description: Use when a Python project ALREADY INSTRUMENTS with LangSmith (the `langsmith` SDK, v0.x) or LangChain's auto-tracing (the `LANGSMITH_TRACING_V2=true` env var) and wants to switch its observability backend to NeatLogs. Walks a 6-step migration: detect LangSmith use (direct vs transitive via LangChain), add NeatLogs init in side-by-side mode, **first try the OTLP-endpoint swap (covers ~90% of v0.x users — change OTEL_EXPORTER_OTLP_ENDPOINT and add the x-api-key header)**, then fall back to mapping LangSmith decorator calls (`@traceable`, `@trace`, `RunTree`) to NeatLogs spans if the project uses the explicit SDK (not the OTel path), then cut over. Test against `langsmith>=0.1,<1.0` and the LangChain v0.3+ observability callback. LangSmith v1 (beta) and `langchain smith` eval CLI are out of scope.
metadata:
  author: neatlogs
  language: python
  framework: langsmith-migration
  tested-against: "langsmith>=0.1,<1.0"
---

# NeatLogs — Migrate from LangSmith to NeatLogs

This skill is for a Python project that already instruments with
LangSmith (the `langsmith` SDK or LangChain auto-tracing) and wants
to switch to NeatLogs. It is not a greenfield install path. Start
with `neatlogs-py` if you have nothing yet.

Most LangSmith users finish this migration by changing 2 environment
variables (step 4). The decorator-mapping fallback (step 5) is only
needed for projects using the explicit `@traceable` SDK path with
custom RunTree logic.

## The two LangSmith v0.x paths

| Path | How you set LangSmith up today | Migration path |
|---|---|---|
| **A. Auto-tracing via OTel** (~90% of users) | You set `LANGSMITH_TRACING_V2=true` + `LANGSMITH_API_KEY=...` and let LangChain's `langchain.observability` callback (or the `langchain.tracing` context manager) export traces via OTel | **Step 4 only.** Change `OTEL_EXPORTER_OTLP_ENDPOINT` and the auth header. No code changes. |
| **B. Explicit `@traceable` SDK** (~10% of users) | You `from langsmith import traceable` (or `from langsmith import trace`) and call `langsmith_client.create_run(...)` / `RunTree(...)` directly | **Steps 4 + 5.** Endpoint swap plus a code pass to replace LangSmith SDK calls with NeatLogs spans. |

Path detection is in step 1 below. Skip step 5 if you're on Path A.

## Steps

1. **Detect LangSmith** → `references/1-detect-langsmith.md`
2. **Set up side-by-side** → `references/2-side-by-side.md`
3. **Add NeatLogs init** → `references/3-add-neatlogs-init.md`
4. **OTLP-endpoint swap** (the 90% path) → `references/4-otlp-endpoint-swap.md`
5. **Decorator mapping** (the 10% fallback — only if step 4 didn't apply) → `references/5-decorator-mapping.md`
6. **Cut over and clean up** → `references/6-cutover.md`
7. **Rollback** (if something breaks) → `references/7-rollback.md`

## Rules (apply to ALL steps)

- **Self-contained.** This skill does not link to other skills in the
  repo. Each step's reference file is standalone. If a per-stack
  detail is needed (e.g. Pydantic-Settings crash on `NEATLOGS_*` env
  vars, the Next.js crypto build error, the GenAI client
  construction order), it is reproduced inline in the relevant step
  file. Do NOT cross-reference
  `../neatlogs-py-langchain/references/...` from this folder —
  loaders that copy a single skill will break.
- **LangSmith stays running until step 6.** Do not uninstall
  `langsmith` or delete its env vars before step 6. Side-by-side
  mode (step 2) requires both backends live. The cutover in step 6
  is the only step that touches the install.
- **One `neatlogs.init()` per process.** If the project already
  calls `init()` somewhere (e.g. another NeatLogs skill ran first,
  or `neatlogs-py-langchain` is already wired up), this skill
  reuses that call. Do not add a second `init()`.
- **Migration is a router + transition guide, not an auto-rewriter.**
  This skill tells you what to do; you do the actual edits. Auto-
  translating `@traceable` to `@neatlogs.span(...)` across a
  codebase is brittle and out of scope.
- **`langchain smith` is OUT OF SCOPE.** That CLI is for LangSmith
  evaluation (datasets + evaluators). NeatLogs has no eval surface
  today. If the project depends on `langchain smith` for CI evals,
  stay on LangSmith for that part — only the observability backend
  is being swapped.

## Live completion gate (wizard or standalone coding agent)

This skill does not grant platform access. The marker-aware `get_trace_context` contract must be deployed on the hosted Neatlogs backend, and the installed SDK or exporter must preserve the resource marker; merged source changes or an updated local wizard alone are not proof.

For the representative run after step 4 (or after step 5 on Path B), generate two distinct UUIDs: a process marker and an exercise nonce. Append `neatlogs.verification.marker=<marker UUID>` to `OTEL_RESOURCE_ATTRIBUTES`, preserving existing entries and scoping it only to the launched process; do not edit source or persistent configuration, and do not treat either value as a secret. Put the exact token `neatlogs-verification:<nonce UUID>` in a safe representative user request, prompt, or API argument that exercises the real path and should be captured in a persisted span `input_value`. Keep LangSmith running for this exercise (side-by-side mode); the marker proves the NeatLogs side independently of whatever LangSmith shows. Immediately before the exercise, record the current UTC timestamp. If the coding agent cannot launch a web UI path, tell the user exactly how to start the app with the temporary marker and which nonce token to submit. If the path cannot safely carry a unique captured input, report that blocker and leave verification incomplete.

After the exercised request finishes, flush telemetry and gracefully stop the marked process or relaunch it without the marker before discovery. If marked trace production cannot be quiesced, leave verification incomplete. Then call the already-connected Neatlogs platform MCP with `get_trace_context(verification_marker=<marker UUID>, candidate_offset=0)`. Enumerate offsets from 0 upward, collecting distinct trace IDs until MCP returns `No project trace found` for the next offset. For every candidate, page its complete span set with `get_trace_context(trace_id=<trace_id>, offset=<next_offset>)` until `next_offset` is null. A candidate qualifies only when the exact nonce token appears in a persisted span `input_value`, its top-level `name` and `workflow` plus parentless root span match the exercised path and the `workflow_name` chosen in step 3, its `created_at` is not earlier than the recorded timestamp, `root_span_count` is 1, and no span has `synthetic_recovery_root: true`. Never select the first or latest marker match. If no trace qualifies yet, poll every 5 seconds and repeat the full enumeration for up to 2 minutes. Restart a scan if offsets shift and duplicate a trace ID; if a complete distinct scan cannot be obtained, offset 100 still returns a candidate, or zero or multiple traces qualify, report the ambiguity and leave verification incomplete.

Once exactly one trace qualifies, poll that exact `trace_id` every 5 seconds for up to 2 minutes while `status` is `processing` or `finalization_status` is `pending`. If it does not reach `finalized` within that bound, leave verification incomplete. Treat a null or unrecognized `finalization_status` as a hosted-contract blocker. After `finalization_status` is `finalized`, require `trace_context_contract_version: 2`, `verification_ready: true`, `span_payload_complete: true`, `span_tree_complete: true`, and `root_span_count: 1`; otherwise report a hosted-contract or incomplete-payload blocker. Page all spans again and perform two identical full marker-candidate enumerations at least 10 seconds apart to confirm that exactly one trace contains the nonce in both scans. Verify that all `span_count` spans were inspected.

If `get_trace_context` rejects `verification_marker`, `candidate_offset`, `trace_id`, or `offset`, or omits `trace_context_contract_version`, `verification_ready`, `span_payload_complete`, `span_tree_complete`, `root_span_count`, `trace_id`, `name`, `workflow`, `created_at`, `spans[].parent_span_id`, `spans[].input_value`, `status`, `finalization_status`, `next_offset`, or `span_count`, treat the hosted MCP as an old contract: stop, report the hosted deployment blocker, and do not claim verification or use another trace query. If MCP is unavailable, ask the user to configure `https://ingest.neatlogs.com/mcp` with the project key stored as a client secret; never print or request the key in chat, and leave verification incomplete.

- Exercise the actual user-facing migrated path. Inspect the full persisted span tree and returned semantic fields, not only a trace-list summary, local debug output, or the LangSmith view. Confirm the nonce-qualified project trace is the fresh run, with one canonical hierarchy and no duplicate LangSmith-side spans. An offline/no-export verifier is insufficient by itself.
- Do not claim the migration verified until all applicable checks pass and step 6's cutover conditions are met. If runtime or ingestion cannot be confirmed, report the exact blocker and leave the result incomplete.

## Quick reference: env vars used by this skill

| Env var | Set in | Purpose |
|---|---|---|
| `NEATLOGS_API_KEY` | step 3 | Auth for the NeatLogs ingest endpoint. Get from the NeatLogs dashboard (Settings → API keys). |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | step 4 | Where OTel exports traces. Change from LangSmith's URL to `https://ingest.neatlogs.com`. |
| `OTEL_EXPORTER_OTLP_HEADERS` | step 4 | OTel headers. Set to `x-api-key=$NEATLOGS_API_KEY`. |
| `LANGCHAIN_TRACING_V2`, `LANGSMITH_TRACING_V2` | step 6 (delete) | Auto-tracing toggles. Disable after side-by-side is verified. |
| `LANGCHAIN_API_KEY`, `LANGSMITH_API_KEY` | step 6 (delete) | Auth for LangSmith's collector. Not needed once LangSmith is cut over. |
| `LANGCHAIN_ENDPOINT`, `LANGSMITH_ENDPOINT` | step 6 (delete) | LangSmith's collector URL. Default is `https://api.smith.langchain.com`. |
| `LANGCHAIN_PROJECT`, `LANGSMITH_PROJECT` | step 4 (rename) | Maps to NeatLogs `workflow_name`. |

## Reference

- Self-contained. No cross-skill links. Each step file is standalone.
- For the broader NeatLogs SDK reference (decorator kinds, span types,
  prompt templates), see `references/span-kinds.md` and
  `references/sessions-and-end-users.md` in this skill folder. They
  reproduce only what's needed for the migration; for the full
  reference, the user reads `neatlogs-py` directly.
