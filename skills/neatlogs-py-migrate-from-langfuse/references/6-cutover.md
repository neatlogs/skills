# Step 6: Cut over and clean up

## Pre-flight

Do not run this step until:

- The NeatLogs dashboard has been receiving traces for at least one
  full request cycle (a single end-to-end test, ideally a real
  production load sample). Step 4 and/or step 5 are confirmed
  working.
- The trace shape on NeatLogs matches what Langfuse was showing:
  same spans, same nesting, same token counts, same session
  grouping.
- A rollback plan is in place (see step 7).

## Action

1. **Remove the second OTel exporter** if step 2 added one
   (the side-by-side pattern). Now that the endpoint points at
   NeatLogs in step 4, the first exporter is still pointing at
   Langfuse — both get every span. Cut over by removing the
   Langfuse-pointing exporter OR by re-pointing it at NeatLogs
   (same effect). The clean cutover is: **delete the Langfuse
   exporter entirely**.

2. **Revert the endpoint swap** is NOT the right cutover direction.
   Step 4 already moved `OTEL_EXPORTER_OTLP_ENDPOINT` to NeatLogs.
   Step 6 is about removing the Langfuse SIDE, not the NeatLogs side.

3. **Uninstall `langfuse`** if it's a direct dep:
   ```bash
   pip uninstall langfuse
   ```
   If `langfuse` is a TRANSITIVE dep (pulled in by a framework
   extra), DO NOT uninstall — that would break the framework. Just
   leave it; the Langfuse integration is no longer being used.

4. **Delete the Langfuse env vars** from `.env` and from any
   deployment configs (Kubernetes secrets, CI variables, etc.):
   ```
   LANGFUSE_PUBLIC_KEY
   LANGFUSE_SECRET_KEY
   LANGFUSE_HOST
   ```
   (If a framework callback is using these, leave them — but they
   no longer route traces anywhere useful.)

5. **Remove the Langfuse OTel env vars** (if step 4 set them):
   - The `OTEL_EXPORTER_OTLP_ENDPOINT` is now NeatLogs — keep it.
   - If `OTEL_EXPORTER_OTLP_HEADERS` contained a Langfuse
     `Authorization: Bearer ...` value, replace it with the
     `x-api-key=$NEATLOGS_API_KEY` value (already done in step 4).

6. **Remove any Langfuse client construction** that the
   decorator-mapping step (5) missed. Grep:
   ```bash
   grep -rnE 'Langfuse\(' . --include='*.py' 2>/dev/null
   ```
   Any remaining hit is leftover from a partial edit; remove it.

7. **Replace any `lf.flush()` / `lf.shutdown()` calls** with
   `neatlogs.flush()` / `neatlogs.shutdown()`. Grep to confirm:
   ```bash
   grep -rnE 'lf\.(flush|shutdown)\(' . --include='*.py' 2>/dev/null
   ```

8. **Update internal docs** if any (README, ARCHITECTURE.md, runbooks
   that mention Langfuse) to point at NeatLogs.

9. **Update the test suite**: any tests that asserted on
   Langfuse-shaped output now assert on NeatLogs. If a test was
   mocking `Langfuse`, replace with mocking `neatlogs` (the
   `neatlogs-validate` skill — added in this PR — can verify the
   new setup end-to-end).

10. **Commit and deploy**. The first commit can be the step 4
    endpoint swap (already in your git history if you committed
    incrementally); the second commit is the step 6 cleanup.
    Push both to the deployment branch.

## What the user should see after step 6

- NeatLogs dashboard: same trace volume as Langfuse was showing
  (or higher, since auto-instrumentation in step 3 may add spans
  Langfuse was not capturing).
- Langfuse dashboard: empty (or only legacy data from before the
  cutover).
- No errors in the application logs about missing `langfuse` or
  unconfigured exporters.

## Common regressions to watch for

- **"extra fields not permitted" crash on import** if `.env` still
  contains Langfuse env vars and the project uses
  `pydantic-settings` with strict extras. Fix per step 3's
  `"extra": "ignore"` recipe.
- **Double spans** if the second OTel exporter from step 2 is
  still active AND the Langfuse-pointing exporter still runs. The
  cutover must remove one of them. Grep for `OTLPSpanExporter` to
  confirm.
- **Orphan Langfuse objects** (a `Langfuse()` instance still
  constructed somewhere but never used). Python will keep them
  alive but they're not exporting — harmless unless `Langfuse()`
  constructor throws when env vars are missing.
