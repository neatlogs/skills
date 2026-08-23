---
name: neatlogs-multi-workflow
description: >
  Language-agnostic guidance for instrumenting a codebase that runs MULTIPLE independent
  workflows/features in one process (e.g. a copilot + a summarizer + a background job) with
  neatlogs, so each shows up as a distinct, filterable workflow in the dashboard. Use this in
  addition to the language skill (neatlogs-py / neatlogs-ts / neatlogs-go) when a single
  service or app has more than one independent feature or agent flow.
metadata:
  author: neatlogs
  language: any
---

# NeatLogs — Multiple Workflows in One Codebase

Most real services do more than one thing: a chat copilot, a summarizer, a report generator, a background evaluation job. Each is an **independent workflow** — its own inputs, its own shape, its own success criteria — and you want them to appear in the NeatLogs dashboard as *separate*, filterable workflows, not one blob.

This skill is **language-agnostic**. Apply it alongside the language skill (`neatlogs-py`, `neatlogs-ts`, `neatlogs-go`) — those cover `init()` and span APIs; this covers how to split one codebase into N workflows.

For managed Neatlogs, do not add an endpoint/base URL option or `NEATLOGS_ENDPOINT`; every SDK defaults to `https://ingest.neatlogs.com`.

Canonical docs: https://docs.neatlogs.com/sdk/multiple-workflows

## Completion gate

Do not report success after editing files alone. Build the affected package or application, restart the real process, and exercise every changed workflow entry point. This skill does not grant platform access. The marker-aware `get_trace_context` contract must be deployed on the hosted Neatlogs backend, and the installed SDK or exporter must preserve the resource marker; merged source changes or an updated local wizard alone are not proof.

Generate one process-marker UUID for each launched process and a distinct exercise-nonce UUID for every changed workflow entry point. Append `neatlogs.verification.marker=<marker UUID>` to `OTEL_RESOURCE_ATTRIBUTES`, preserving existing entries and scoping it only to the launched process; do not edit source or persistent configuration, and do not treat either value as a secret. Put each exact token `neatlogs-verification:<nonce UUID>` in a safe representative user request, prompt, or API argument for its workflow so it should be captured in a persisted span `input_value`. Record the current UTC timestamp before the exercises. If the coding agent cannot launch a web UI path, tell the user exactly how to start the app with the temporary marker and which nonce token to submit for each workflow. If any path cannot safely carry a unique captured input, report that blocker and leave its verification incomplete.

After the exercises finish, flush telemetry and gracefully stop the marked process or relaunch it without the marker before discovery. If marked trace production cannot be quiesced, leave verification incomplete. Call the already-connected Neatlogs platform MCP with `get_trace_context(verification_marker=<marker UUID>, candidate_offset=0)`. Enumerate offsets from 0 upward, collecting distinct trace IDs until MCP returns `No project trace found` for the next offset. Page every candidate completely with `get_trace_context(trace_id=<trace_id>, offset=<next_offset>)` until `next_offset` is null. Match a candidate to a workflow only when exactly that workflow's nonce appears in a persisted span `input_value`, its top-level `name` and `workflow` plus parentless root span match the exercised entry point, its `created_at` is not earlier than the recorded timestamp, `root_span_count` is 1, and no span has `synthetic_recovery_root: true`. Never select the first or latest marker match. If no workflow trace qualifies yet, poll every 5 seconds and repeat the full enumeration for up to 2 minutes. Restart a scan if offsets shift and duplicate a trace ID; if a complete distinct scan cannot be obtained, offset 100 still returns a candidate, any nonce matches zero or multiple traces, or one trace matches multiple workflow nonces, report the ambiguity and leave verification incomplete.

For each uniquely matched trace, poll its exact `trace_id` every 5 seconds for up to 2 minutes while `status` is `processing` or `finalization_status` is `pending`. If any trace does not reach `finalized` within that bound, leave verification incomplete. Treat a null or unrecognized `finalization_status` as a hosted-contract blocker. After all are `finalized`, require `trace_context_contract_version: 2`, `verification_ready: true`, `span_payload_complete: true`, `span_tree_complete: true`, and `root_span_count: 1` on each trace; otherwise report a hosted-contract or incomplete-payload blocker. Page every span again and perform two identical full marker-candidate enumerations at least 10 seconds apart to confirm the same one-to-one nonce/trace mapping in both scans. Verify that all `span_count` spans in every matched trace were inspected.

If `get_trace_context` rejects `verification_marker`, `candidate_offset`, `trace_id`, or `offset`, or omits `trace_context_contract_version`, `verification_ready`, `span_payload_complete`, `span_tree_complete`, `root_span_count`, `trace_id`, `name`, `workflow`, `created_at`, `spans[].parent_span_id`, `spans[].input_value`, `status`, `finalization_status`, `next_offset`, or `span_count`, treat the hosted MCP as an old contract: stop, report the hosted deployment blocker, and do not claim verification or use another trace query. If MCP is unavailable, ask the user to configure `https://ingest.neatlogs.com/mcp` with the project key stored as a client secret; never print or request the key in chat.

Inspect each full persisted span tree, top-level `workflow`, and parentless root span, not only a trace-list summary or local debug output. Confirm every fresh trace is assigned to the intended workflow. If any workflow cannot be built, restarted, run, or verified, state that the instrumentation is incomplete and identify the exact blocker.

---

## Core rule

**`init()` is process-wide and single-shot.** Its `workflow_name` is ONE label for the whole process; calling `init()` again with a different name is a no-op. So you do **not** create multiple workflows by calling `init()` multiple times in one process.

To get N workflows from one codebase, **declare each workflow at its entry point** — the place where that feature's call first starts (the request handler, the job function, the queue-consumer callback) — by opening a named `WORKFLOW` root there, and **overriding the workflow label** on that root.

---

## The two levels

A large service uses both:

1. **Separate process / boot path → separate `init()`.** Two things that boot independently (an HTTP server + a standalone worker; a main app + a mounted sub-app) each call `init()` with their own `workflow_name`. This works *because* they are separate boot paths.
2. **One process, many features → one `init()`, a named root per feature.** The common case. Inside a single process, each feature opens its own `WORKFLOW` root where its work starts. This skill focuses here.

---

## Name vs. workflow — two different dashboard dimensions

| Dimension | What it is | Set by |
|---|---|---|
| **Root span name** | The **title** of an individual trace | The `name` passed when opening the root |
| **Workflow** | The **group** a trace belongs to (dashboard Workflow column / filter / analytics) | Process default from `init(workflow_name=...)` / `init({ workflowName })`; canonical per-root override `neatlogs.workflow.name` |

> ⚠️ **Naming the root span is NOT enough to make a distinct workflow.** The span name is the trace title; the Workflow dimension uses the process default unless the root sets canonical `neatlogs.workflow.name`. If a feature only opens a differently-*named* root but never sets that attribute, it still rolls up under the single `init()` workflow. Convention: use the same human-readable string for both the root name and the workflow override so the trace title and Workflow column agree.

---

## The pattern per language

Open the root at the FIRST line of the feature's work, and set the label there.

### Python

Set the canonical per-root `neatlogs.workflow.name` attribute with `set_attribute`:

```python
import neatlogs

neatlogs.init(api_key=..., workflow_name="my-service")  # process-wide default

@app.post("/copilot/chat")
async def copilot_chat(req):
    with neatlogs.trace("Copilot chat", kind="WORKFLOW") as root:
        root.set_attribute("neatlogs.workflow.name", "Copilot chat")
        return await run_copilot(req)
```

A helper keeps entry points to one call:

```python
from contextlib import contextmanager

@contextmanager
def workflow(name: str):
    with neatlogs.trace(name, kind="WORKFLOW") as root:
        root.set_attribute("neatlogs.workflow.name", name)
        yield root

with workflow("Report generation"):
    ...
```

### TypeScript

Set the per-root label via `attributes` (dot-form `neatlogs.workflow.name`):

```typescript
import { trace } from 'neatlogs';

await trace(
  { name: 'Copilot chat', kind: 'WORKFLOW', attributes: { 'neatlogs.workflow.name': 'Copilot chat' } },
  async () => runCopilot(req),
);
```

You can also `span.setAttribute('neatlogs.workflow.name', 'Copilot chat')` inside the callback. The process-global `neatlogs.workflow_name` from `init()` is not overwritten.

### Go

`Trace(ctx, name)` takes no options, so use `StartSpan` with the `neatlogs.workflow.name` attribute (or `SetAttributes` on the root):

```go
import "go.opentelemetry.io/otel/attribute"

ctx, span, end := neatlogs.StartSpan(ctx, "Copilot chat", "workflow",
    attribute.String("neatlogs.workflow.name", "Copilot chat"))
defer end()
_ = span
```

`neatlogs.Trace(ctx, name)` is the shorthand when a named root is enough and you're happy for it to roll up under the `Init` workflow name.

---

## Choosing workflow boundaries

Treat each as its own workflow:

- **Distinct product features** — copilot, summarizer, autocomplete, report generator.
- **Distinct trigger types for the same logic** — synchronous API path vs. background/queue path, if you want them analyzed separately.
- **Distinct jobs in a worker** — each scheduled or event-driven job function.

Keep it **one workflow per feature area**, not per request and not per file. Use a stable, human-readable label. Environment/version → [tags](https://docs.neatlogs.com/sdk/tags); per-user/per-conversation → [sessions](https://docs.neatlogs.com/sdk/sessions) / [end-user identity](https://docs.neatlogs.com/sdk/end-user-identity) — none of these belong in the workflow name.

---

## Reference implementation

The NeatLogs AI service (one FastAPI process) is the canonical example:

- **One `init(workflow_name="AI Service")`** as the coarse process fallback.
- **Each feature opens its own `WORKFLOW` root at its handler and overrides the label** — adapt the names to the application's real features — via a shared helper that calls `span.set_attribute("neatlogs.workflow.name", <label>)` on the root plus tenant/session attributes. The backend prefers this per-root value over the process default for the trace's Workflow column.
- **A separately-booted sub-app runs its own `init(workflow_name="Neatlogs Harness")`** — level 1 (separate boot path → separate workflow).
- Features that only name the root but skip the override still roll up under `"AI Service"` — proof that the override, not the span name, carves out a distinct workflow.
