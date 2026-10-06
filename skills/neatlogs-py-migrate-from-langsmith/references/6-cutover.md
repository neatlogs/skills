# Step 6: Cut over and clean up

## Pre-flight

Do not run this step until:

- The SKILL.md live completion gate has passed on a
  representative request: a marker-matched, nonce-qualified trace
  was found through `get_trace_context`, fully paged, and every
  persisted span inspected. Step 4 and/or step 5 are confirmed
  working against persisted data, not a dashboard glance.
- The persisted trace shape matches what LangSmith was showing:
  same spans, same nesting, same token counts, same session
  grouping.
- A rollback plan is in place (see step 7).

## Action

1. **Remove the second OTel exporter** if step 2 added one (the
   side-by-side pattern). Now that the endpoint points at
   NeatLogs in step 4, the first exporter is still pointing at
   LangSmith — both get every span. Cut over by removing the
   LangSmith-pointing exporter OR by re-pointing it at NeatLogs
   (same effect). The clean cutover is: **delete the LangSmith
   exporter entirely**.

2. **Revert the endpoint swap** is NOT the right cutover
   direction. Step 4 already moved `OTEL_EXPORTER_OTLP_ENDPOINT`
   to NeatLogs. Step 6 is about removing the LangSmith SIDE,
   not the NeatLogs side.

3. **Disable LangSmith auto-tracing**. The critical env vars:
   ```
   LANGSMITH_TRACING_V2=false      # or unset
   LANGCHAIN_TRACING_V2=false      # older LangChain v0.2
   ```
   Setting these to `false` is the single env-var change that
   stops the LangChain `langchain.observability` callback from
   pushing to LangSmith. If you set them to anything other than
   `false` (e.g. `true` or empty), LangChain may fall through to
   a default that re-enables tracing.

4. **Uninstall `langsmith`** if it's a direct dep:
   ```bash
   pip uninstall langsmith
   ```
   If `langsmith` is a TRANSITIVE dep (pulled in by LangChain's
   `langchain_community` or `langchain[tracing]` extra), DO NOT
   uninstall — that would break LangChain. Just leave it; the
   LangSmith integration is no longer being used.

5. **Delete the LangSmith env vars** from `.env` and from any
   deployment configs (Kubernetes secrets, CI variables, etc.):
   ```
   LANGCHAIN_TRACING_V2
   LANGSMITH_TRACING_V2
   LANGCHAIN_API_KEY
   LANGSMITH_API_KEY
   LANGCHAIN_ENDPOINT
   LANGSMITH_ENDPOINT
   ```
   (If a LangChain callback is still using these, leave them —
   but they no longer route traces anywhere useful.)

6. **Rename `LANGCHAIN_PROJECT` / `LANGSMITH_PROJECT`** if you
   want it to match your new `workflow_name` (already done in
   step 3). Otherwise, delete it.

7. **Remove any LangSmith client construction** that the
   decorator-mapping step (5) missed. Grep:
   ```bash
   grep -rnE 'langsmith_client\.|langsmith\.Client\(|RunTree\(' . --include='*.py' 2>/dev/null
   ```
   Any remaining hit is leftover from a partial edit; remove it.

8. **Replace any `langsmith_client.flush()` / `delete_project()`**
   calls with `neatlogs.flush()` (or remove — projects are
   derived from `workflow_name`).

9. **Update internal docs** if any (README, ARCHITECTURE.md,
   runbooks that mention LangSmith) to point at NeatLogs.

10. **Update the test suite**: any tests that asserted on
    LangSmith-shaped output now assert on NeatLogs. If a test
    was mocking `langsmith_client`, replace with mocking
    `neatlogs` (the `neatlogs-validate` skill — added in a
    separate PR — can verify the new setup end-to-end).

11. **Commit and deploy**. The first commit can be the step 4
    endpoint swap (already in your git history if you committed
    incrementally); the second commit is the step 6 cleanup.
    Push both to the deployment branch.

## What the user should see after step 6

- NeatLogs dashboard: same trace volume as LangSmith was showing
  (or higher, since auto-instrumentation in step 3 may add
  spans LangSmith was not capturing).
- LangSmith dashboard: empty (or only legacy data from before
  the cutover).
- No errors in the application logs about missing `langsmith`
  or unconfigured exporters.

## Common regressions to watch for

- **"extra fields not permitted" crash on import** if `.env`
  still contains LangSmith env vars and the project uses
  `pydantic-settings` with strict extras. Fix per step 3's
  `"extra": "ignore"` recipe.
- **Double spans** if the second OTel exporter from step 2 is
  still active AND the LangSmith-pointing exporter still runs.
  The cutover must remove one of them. Grep for
  `OTLPSpanExporter` to confirm.
- **`langchain.observability` keeps pushing to LangSmith** if
  `LANGSMITH_TRACING_V2=true` is still set. Step 6.3 must
  explicitly set it to `false`. The empty / unset state is
  risky because LangChain's default is to NOT auto-trace, but
  custom integrations in `langchain.observability` may have
  their own defaults.
- **Orphan LangSmith objects** (a `langsmith.Client()` instance
  still constructed somewhere but never used). Python will
  keep them alive but they're not exporting — harmless unless
  `Client()` constructor throws when `LANGSMITH_API_KEY` is
  missing.
