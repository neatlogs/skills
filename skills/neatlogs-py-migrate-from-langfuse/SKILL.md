---
name: neatlogs-py-migrate-from-langfuse
description: Use when a Python project ALREADY INSTRUMENTS with Langfuse (v2.x) and wants to switch its observability backend to NeatLogs. Walks a 6-step migration: detect Langfuse use (direct vs transitive), add NeatLogs init in side-by-side mode, **first try the OTLP-endpoint swap (covers ~90% of v2 users — change OTEL_EXPORTER_OTLP_ENDPOINT and add the x-api-key header)**, then fall back to mapping Langfuse decorator calls to NeatLogs spans if the project uses the native Langfuse SDK (not the OTel path), then cut over. Test against Langfuse v2.x; v1.x is a different shape and is out of scope (v1 users should upgrade to v2 first).
metadata:
  author: neatlogs
  language: python
  framework: langfuse-migration
  tested-against: "langfuse>=2.0,<3.0"
---

# NeatLogs — Migrate from Langfuse to NeatLogs

This skill is for a Python project that **already instruments with
Langfuse** and wants to switch to NeatLogs. It is **not** a greenfield
install path — start with `neatlogs-py` if you have nothing yet.

The headline insight: **most Langfuse v2 users can finish this migration
by changing 2 environment variables** (step 4). The decorator-mapping
fallback (step 5) is only needed for projects on the native Langfuse SDK
path.

## The two Langfuse v2 paths (read first — which one are you on?)

| Path | How you set Langfuse up today | Migration path |
|---|---|---|
| **A. OTel exporter** (90% of v2 users) | You set `OTEL_EXPORTER_OTLP_ENDPOINT=...langfuse...` and use a plain OTel SDK (`opentelemetry-instrumentation-*` or `@trace`-style decorators on `OpenAI()` etc.) | **Step 4 only** — change the endpoint + add the x-api-key header. No code changes. |
| **B. Native Langfuse SDK** (10% of v2 users) | You `from langfuse import Langfuse; lf = Langfuse(...)` and call `lf.update_current_span(...)` / `lf.score_current_span(...)` / `@observe()` | **Steps 4 + 5** — endpoint swap plus a code pass to replace Langfuse SDK calls with NeatLogs spans. |

Path detection is in step 1 below. Skip step 5 if you're on Path A.

## Steps

1. **Detect Langfuse** → `references/1-detect-langfuse.md`
2. **Set up side-by-side** → `references/2-side-by-side.md`
3. **Add NeatLogs init** → `references/3-add-neatlogs-init.md`
4. **OTLP-endpoint swap** (the 90% path) → `references/4-otlp-endpoint-swap.md`
5. **Decorator mapping** (the 10% fallback — only if step 4 didn't apply) → `references/5-decorator-mapping.md`
6. **Cut over and clean up** → `references/6-cutover.md`
7. **Rollback** (if something breaks) → `references/7-rollback.md`

## Rules (apply to ALL steps)

- **Self-contained.** This skill does not link to other skills in the
  repo. Each step's reference file is standalone. If a per-stack
  detail is needed (e.g. Pydantic-Settings crash on `NEATLOGS_*` env vars,
  the Next.js crypto build error, the GenAI client construction order),
  it is reproduced inline in the relevant step file. Do NOT cross-
  reference `../neatlogs-py-openai/references/...` from this folder —
  loaders that copy a single skill will break.
- **Langfuse stays running until step 6.** Do not uninstall `langfuse` or
  delete its env vars before step 6. Side-by-side mode (step 2) requires
  both backends live. The cutover in step 6 is the only step that
  touches the install.
- **One `neatlogs.init()` per process.** If the project already calls
  `init()` somewhere (e.g. another NeatLogs skill ran first), this skill
  reuses that call. Do not add a second `init()`.
- **Migration is a router + transition guide, not an auto-rewriter.**
  This skill tells you what to do; you do the actual edits. Auto-
  translating `@observe()` to `@neatlogs.span(...)` across a codebase
  is brittle and out of scope.

## Quick reference: env vars used by this skill

| Env var | Set in | Purpose |
|---|---|---|
| `NEATLOGS_API_KEY` | step 3 | Auth for the NeatLogs ingest endpoint. Get from the NeatLogs dashboard (Settings → API keys). |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | step 4 | Where OTel exports traces. Change from Langfuse's URL to `https://ingest.neatlogs.com`. |
| `OTEL_EXPORTER_OTLP_HEADERS` | step 4 | OTel headers. Set to `x-api-key=$NEATLOGS_API_KEY`. |
| `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST` | step 6 (delete) | Only needed for the native Langfuse SDK path; not required once side-by-side is verified. |

## Reference

- Self-contained. No cross-skill links. Each step file is standalone.
- For the broader NeatLogs SDK reference (decorator kinds, span types,
  prompt templates), see `references/span-kinds.md` and
  `references/sessions-and-end-users.md` in this skill folder — they
  reproduce only what's needed for the migration; for the full
  reference, the user can read `neatlogs-py` directly.
