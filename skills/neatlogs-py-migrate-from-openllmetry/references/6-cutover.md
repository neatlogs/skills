# Step 6: Cut over with live-trace verification (the 1.2.4 gate)

## Pre-flight

Do not run this step until:

- The NeatLogs dashboard has been receiving traces for at
  least one full request cycle (a single end-to-end test,
  ideally a real production load sample). Step 4 and/or
  step 5 are confirmed working.
- The trace shape on NeatLogs matches what your previous
  OTel collector was showing: same spans, same nesting,
  same token counts, same session grouping.
- The live completion gate in the SKILL.md is reachable
  (the hosted NeatLogs MCP at `https://ingest.neatlogs.com/mcp`
  is configured and responds to `get_trace_context`).
- A rollback plan is in place (see step 7).

## Action

### A. Remove the side-by-side exporter (Path A) or the dual OTel chain (Path B)

1. **Remove the second OTel exporter** if step 2 added one.
   Now that the endpoint points at NeatLogs in step 4, the
   first exporter is still pointing at your previous
   collector — both get every span. Cut over by removing the
   previous-collector-pointing exporter OR by re-pointing it
   at NeatLogs (same effect). The clean cutover is: **delete
   the previous-collector exporter entirely**.
2. **Revert the endpoint swap** is NOT the right cutover
   direction. Step 4 already moved
   `OTEL_EXPORTER_OTLP_ENDPOINT` to NeatLogs. Step 6 is
   about removing the OpenLLMetry SIDE, not the NeatLogs side.
3. **Uninstall `opentelemetry-instrumentation-*` and
   `openinference-*`** if they're direct deps:
   ```bash
   pip uninstall opentelemetry-instrumentation-openai openinference-instrumentation-openai
   ```
   (The exact package list depends on what step 1 found. If
   the project has 5 instrumentors, uninstall all 5.)
   If they're TRANSITIVE deps (pulled in by a framework
   extra), DO NOT uninstall — that would break the framework.
   Just leave them; the OpenLLMetry integration is no longer
   being used.
4. **Delete the OTel env vars** from `.env` and from any
   deployment configs (Kubernetes secrets, CI variables,
   etc.):
   ```
   OTEL_EXPORTER_OTLP_ENDPOINT
   OTEL_EXPORTER_OTLP_HEADERS
   OTEL_SERVICE_NAME  (only if you want a different value; the workflow_name in step 3 takes over)
   ```
5. **Remove any `tracer = trace.get_tracer(...)` and
   `trace.set_tracer_provider(...)` calls** that the
   decorator-mapping step (5) missed. Grep:
   ```bash
   grep -rnE 'trace\.get_tracer\(|trace\.set_tracer_provider\(' . --include='*.py' 2>/dev/null
   ```
6. **Update internal docs** if any (README, ARCHITECTURE.md,
   runbooks that mention OpenLLMetry / OpenTelemetry) to
   point at NeatLogs.
7. **Update the test suite**: any tests that asserted on
   OpenLLMetry / OpenInference output now assert on
   NeatLogs. If a test was mocking OpenLLMetry, replace with
   mocking `neatlogs` (the `neatlogs-validate` skill can
   verify the new setup end-to-end).
8. **Commit and deploy**. The first commit can be the step 4
   endpoint swap (already in your git history if you
   committed incrementally); the second commit is the step 6
   cleanup. Push both to the deployment branch.

### B. Run the live completion gate

The gate is fully specified in the SKILL.md's "Live
completion gate" section. The short version:

1. Generate a process marker UUID and an exercise nonce UUID.
2. Append `neatlogs.verification.marker=<marker UUID>` to
   `OTEL_RESOURCE_ATTRIBUTES` for the launched process (do
   NOT commit it; pass it as an env var to the start
   command).
3. Put the token `neatlogs-verification:<nonce UUID>` in a
   representative user input that exercises the real
   migrated path. Do not start with a fresh project; pick
   the user-facing route the migration actually serves.
4. Record the current UTC timestamp immediately before the
   exercise.
5. After the exercise, flush telemetry and either stop the
   marked process or relaunch it without the marker.
6. Call the hosted NeatLogs MCP
   (`https://ingest.neatlogs.com/mcp`) with
   `get_trace_context(verification_marker=<marker UUID>,
   candidate_offset=0)`. Enumerate offsets from 0 upward
   until MCP returns "No project trace found". Page every
   candidate's full span set.
7. The candidate qualifies only when the exact nonce token
   appears in a persisted span `input_value`, the top-level
   `name` and `workflow` plus parentless root span match
   the exercised path and the `workflow_name` from step 3,
   `created_at` is not earlier than the recorded timestamp,
   `root_span_count` is 1, and no span has
   `synthetic_recovery_root: true`.
8. Poll that exact `trace_id` every 5 seconds for up to 2
   minutes until `finalization_status` is `finalized`.
9. After finalization, require `trace_context_contract_version:
   2`, `verification_ready: true`, `span_payload_complete:
   true`, `span_tree_complete: true`, `root_span_count: 1`.
10. Page all spans again and perform two identical full
    marker-candidate enumerations at least 10 seconds apart
    to confirm that exactly one trace contains the nonce in
    both scans. Verify that all `span_count` spans were
    inspected.
11. If any step returns 0 qualifying traces, multiple
    qualifying traces, or fails the hosted-contract check,
    report the exact blocker and leave verification
    incomplete. Do NOT claim the migration verified.

### C. The MCP call (if your environment supports it)

```python
# Using the NeatLogs MCP (configured per SKILL.md "Live completion gate")
import asyncio
from mcp import Client

async def verify():
    client = await Client.connect("https://ingest.neatlogs.com/mcp")
    # ... (enumeration, polling, finalization per SKILL.md gate)
```

If the MCP is not configured, ask the user to set it up
before claiming verification. Do not skip the gate.

## What the user should see after step 6

- NeatLogs dashboard: same trace volume as your previous OTel
  collector was showing (or higher, since auto-instrumentation
  in step 3 may add spans OpenLLMetry was not capturing).
- Previous OTel collector: empty (or only legacy data from
  before the cutover).
- No errors in the application logs about missing
  `opentelemetry-instrumentation-*` or unconfigured
  exporters.

## Common regressions to watch for

- **"extra fields not permitted" crash on import** if `.env`
  still contains OTel env vars and the project uses
  `pydantic-settings` with strict extras. Fix per step 3's
  `"extra": "ignore"` recipe.
- **Double spans** if the second OTel exporter from step 2
  is still active AND the previous-collector-pointing
  exporter still runs. The cutover must remove one of them.
  Grep for `OTLPSpanExporter` to confirm.
- **Auto-instrumentation gone silent** if the
  `TracerProvider` was overridden mid-process. The live-
  trace gate catches this (0 qualifying traces is a signal);
  refactor to keep the default OTel global and use
  `@neatlogs.span` for NeatLogs-specific spans.
- **`openinference.span.kind` no longer drives grouping** if
  the OpenInference attributes are dropped but the NeatLogs
  `@neatlogs.span(kind=...)` decorators were not added. The
  live-trace gate's `name` and `workflow` checks still pass,
  but the per-span `kind` is now the default (CHAIN). Fix by
  back-filling `@neatlogs.span(kind=...)` in step 5.
