# Step 7: Rollback

## When to use this

Use this step if at any point after step 4 the NeatLogs side
breaks in a way that can't be fixed in a few minutes — and the
project needs its LangSmith observability back immediately while
a fix is developed.

## What "rollback" means

Restore the original LangSmith routing in a single env-var flip,
without touching code. The NeatLogs init and span code stays in
the codebase but is a no-op (the NeatLogs dashboard will not
receive new traces). This is the cleanest rollback: the app goes
back to exactly the state it was in before the migration started,
and you keep the migration code in git for the next attempt.

## Action

1. **Re-enable LangSmith auto-tracing**:
   ```bash
   # In .env (or wherever the env vars live):
   LANGSMITH_TRACING_V2=true     # or LANGCHAIN_TRACING_V2=true for older LangChain
   LANGCHAIN_TRACING_V2=true     # belt-and-braces
   LANGSMITH_API_KEY=lsv2_pt_...
   LANGCHAIN_API_KEY=lsv2_pt_...
   LANGCHAIN_PROJECT=my-app
   LANGSMITH_PROJECT=my-app
   ```
   Restore the LangSmith endpoint if it was deleted from `.env`
   in step 6:
   ```bash
   OTEL_EXPORTER_OTLP_ENDPOINT=https://api.smith.langchain.com
   OTEL_EXPORTER_OTLP_HEADERS=x-api-key=${LANGSMITH_API_KEY}
   ```

2. **Remove the NeatLogs second OTel exporter** if step 2
   added one. With the endpoint back to LangSmith, the second
   exporter would still send to NeatLogs — leave it disabled,
   or remove it, depending on whether you want the NeatLogs
   dashboard to keep receiving traces during the rollback
   period (useful for debugging).

3. **Revert any decorator-mapping edits from step 5**. If
   step 5 renamed `@traceable(...)` to `@neatlogs.span(...)`,
   the project is now broken at boot — `@traceable` no longer
   exists in the imports. Re-add `from langsmith import
   traceable` and revert the decorator names. If step 5's edits
   are in a single commit, `git revert <commit-sha>` is the
   cleanest revert.

4. **Revert any `init()`-related changes** that broke startup.
   If step 3 added `neatlogs.init()` and a Pydantic-Settings
   crash followed, comment out the `neatlogs.init()` call (do
   not delete it — you'll need it for the next attempt) and
   revert the `model_config` to its original form (drop
   `"extra": "ignore"` for now; add it back in the next attempt
   with the `neatlogs-validate` skill's help).

5. **Restart the application**. Verify LangSmith traces are
   appearing in the LangSmith dashboard again.

6. **Do NOT delete the migration code**. The git history
   keeps step 1-6 commits; you can branch from them and try a
   different approach (different endpoint format, different
   decorator mapping, NeatLogs version bump). The rollback is
   a TEMPORARY state — the migration is not "abandoned", it's
   "paused".

## When rollback is the right call

- The NeatLogs dashboard is consistently empty after step 4
  (no spans arriving for 30+ minutes, network checks out, key
  valid).
- Production errors spike as a direct result of step 3-6 edits
  (e.g. import errors from step 5's decorator rename that a
  partial revert missed).
- A LangSmith-specific business process is failing because
  the LangSmith API is no longer being called. (Unusual; most
  projects just use LangSmith for observability. If you depend
  on LangSmith-specific features — datasets, evaluators,
  feedback surfaces — those are NOT replaced by NeatLogs. Step
  1 should have caught that and recommended you stay on
  LangSmith for those features.)

## When rollback is the WRONG call

- NeatLogs dashboard is empty but only for a few minutes.
  OTel pipelines can take 1-2 minutes to flush the first batch
  on cold start. Wait 5 minutes before rolling back.
- Some spans are missing but not all. This is a partial-
  migration problem, not a migration-broke-everything problem.
  Diagnose the missing pieces — likely a code path that wasn't
  covered by the decorator mapping in step 5. Re-run step 5
  on the new files (step 1's grep result will find them).

## LangChain-specific rollback caveats

If your project uses LangChain's `langchain.observability`
callback (v0.3+), the rollback is a single env-var flip:
`LANGSMITH_TRACING_V2=true` brings back the callback. No code
change needed.

If your project uses the older `langchain.tracing` context
manager (v0.2), you may need to also re-enable
`LANGCHAIN_TRACING_V2=true` for the context manager to be
active. Both `LANGCHAIN_TRACING_V2` and `LANGSMITH_TRACING_V2`
are sometimes set in the same project for forward/backward
compatibility.

## After the rollback

Open an issue or note in the migration project tracking:

- What broke (with trace IDs / dashboard screenshots).
- What was tried in the rollback.
- The next attempt's plan (often: a smaller migration slice,
  or a different LangSmith version's behavior to test against).

The migration skill's value is in the next attempt, not this
one.
