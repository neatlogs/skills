# Step 7: Rollback

## When to use this

Use this step if at any point after step 4 the NeatLogs side
breaks in a way that can't be fixed in a few minutes — and the
project needs its OpenLLMetry observability back immediately
while a fix is developed.

## What "rollback" means

Restore the original OpenLLMetry routing in a single env-var
flip, without touching code. The NeatLogs init and span code
stays in the codebase but is a no-op (the NeatLogs dashboard
will not receive new traces). This is the cleanest rollback:
the app goes back to exactly the state it was in before the
migration started, and you keep the migration code in git for
the next attempt.

## Action

1. **Re-point the OTel endpoint + headers** to your previous
   collector:
   ```bash
   # In .env (or wherever the env vars live):
   OTEL_EXPORTER_OTLP_ENDPOINT=https://your-collector.example.com
   OTEL_EXPORTER_OTLP_HEADERS=Authorization=Bearer%20${COLLECTOR_TOKEN}
   OTEL_SERVICE_NAME=my-app
   ```
   (Replace with the values you had before step 4. The
   `OTEL_EXPORTER_OTLP_HEADERS` shape depends on your
   collector — Phoenix, Tempo, Honeycomb, Jaeger, Datadog
   each use different auth schemes.)

2. **Remove the NeatLogs second OTel exporter** if step 2
   added one. With the endpoint back to your previous
   collector, the second exporter would still send to
   NeatLogs — leave it disabled, or remove it, depending on
   whether you want the NeatLogs dashboard to keep receiving
   traces during the rollback period (useful for debugging).

3. **Revert any decorator-mapping edits from step 5**. If
   step 5 renamed a function-decorator pattern to
   `@neatlogs.span(...)`, the project may now be missing
   span coverage it had before. Re-add
   `from opentelemetry...` imports and revert the decorator
   changes. If step 5's edits are in a single commit,
   `git revert <commit-sha>` is the cleanest revert.

4. **Revert any `init()`-related changes** that broke
   startup. If step 3 added `neatlogs.init()` and a
   Pydantic-Settings crash followed, comment out the
   `neatlogs.init()` call (do not delete it — you'll need
   it for the next attempt) and revert the `model_config`
   to its original form (drop `"extra": "ignore"` for now;
   add it back in the next attempt with the
   `neatlogs-validate` skill's help).

5. **Restart the application**. Verify your previous OTel
   collector traces are appearing in that collector's
   dashboard again.

6. **Do NOT delete the migration code**. The git history
   keeps step 1-6 commits; you can branch from them and try
   a different approach (different endpoint format,
   different decorator mapping, NeatLogs version bump). The
   rollback is a TEMPORARY state — the migration is not
   "abandoned", it's "paused".

## When rollback is the right call

- The NeatLogs dashboard is consistently empty after step 4
  (no spans arriving for 30+ minutes, network checks out,
  key valid).
- The live-trace gate in step 6 returns 0 qualifying
  traces for 2 minutes (no `finalized` candidate, hosted-
  contract check passes, the marker-nonce mechanism is
  correct) — NeatLogs is not persisting the spans.
- Production errors spike as a direct result of step 3-6
  edits (e.g. import errors from step 5's decorator
  rewrite that a partial revert missed).
- An OpenLLMetry-specific business process is failing
  because the OTel collector is no longer being called.
  (Unusual; most projects just use OTel for observability.
  If you depend on OpenInference-specific features —
  Phoenix eval API, OpenInference `evaluator` package —
  those are NOT replaced by NeatLogs. Step 1 should have
  caught that and recommended you stay on OpenLLMetry for
  those features.)

## When rollback is the WRONG call

- NeatLogs dashboard is empty but only for a few minutes.
  OTel pipelines can take 1-2 minutes to flush the first
  batch on cold start. Wait 5 minutes before rolling back.
- Some spans are missing but not all. This is a partial-
  migration problem, not a migration-broke-everything
  problem. Diagnose the missing pieces — likely a code path
  that wasn't covered by the decorator mapping in step 5.
  Re-run step 5 on the new files (step 1's grep result
  will find them).
- The live-trace gate returned a hosted-contract blocker
  (e.g. `trace_context_contract_version` was missing).
  That's a backend issue, not a migration issue. Report it
  to the maintainers; do not roll back.

## After the rollback

Open an issue or note in the migration project tracking:

- What broke (with trace IDs / dashboard screenshots).
- What was tried in the rollback.
- The next attempt's plan (often: a smaller migration
  slice, or a different OTel version's behavior to test
  against).

The migration skill's value is in the next attempt, not
this one.
