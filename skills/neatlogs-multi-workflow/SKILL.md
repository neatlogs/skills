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

Canonical docs: https://docs.neatlogs.com/sdk/multiple-workflows

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
| **Workflow** | The **group** a trace belongs to (dashboard Workflow column / filter / analytics) | The `neatlogs.workflow_name` label — process default from `init()`, or a per-root override |

> ⚠️ **Naming the root span is NOT enough to make a distinct workflow.** The span name is the trace title; the Workflow dimension is driven by the `neatlogs.workflow_name` label. If a feature only opens a differently-*named* root but never overrides the label, it still rolls up under the single `init()` workflow. **Set the per-root override.** Convention: use the same human-readable string for both the root name and the workflow override so the trace title and Workflow column agree.

---

## The pattern per language

Open the root at the FIRST line of the feature's work, and set the label there.

### Python

`neatlogs.workflow_name` isn't a valid Python keyword, so set it with `set_attribute` on the root span:

```python
import neatlogs

neatlogs.init(api_key=..., workflow_name="my-service")  # process-wide default

@app.post("/copilot/chat")
async def copilot_chat(req):
    with neatlogs.trace("Copilot chat", kind="WORKFLOW") as root:
        root.set_attribute("neatlogs.workflow_name", "Copilot chat")   # <- makes it its own workflow
        return await run_copilot(req)
```

A helper keeps entry points to one call:

```python
from contextlib import contextmanager

@contextmanager
def workflow(name: str):
    with neatlogs.trace(name, kind="WORKFLOW") as root:
        root.set_attribute("neatlogs.workflow_name", name)
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
- **Each feature opens its own `WORKFLOW` root at its handler and overrides the label** — Copilot chat, the trace summarizer, the form builder, suggestion generation — via a shared helper that calls `span.set_attribute("neatlogs.workflow_name", <label>)` on the root plus tenant/session attributes. The backend prefers this per-root value over the process default for the trace's Workflow column.
- **A separately-booted sub-app runs its own `init(workflow_name="Neatlogs Harness")`** — level 1 (separate boot path → separate workflow).
- Features that only name the root but skip the override still roll up under `"AI Service"` — proof that the override, not the span name, carves out a distinct workflow.
