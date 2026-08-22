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
