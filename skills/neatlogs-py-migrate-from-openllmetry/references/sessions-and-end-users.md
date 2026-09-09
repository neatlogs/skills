# Sessions & End-Users — for the migration

## Why

Attaching a **session** and an **end-user** to traces turns
raw telemetry into customer analytics: usage / cost / errors
per user and per segment, multi-turn conversation timelines,
and per-customer replay. OpenLLMetry uses the OTel standard
(`session.id` resource attribute, `enduser.id` resource
attribute). NeatLogs uses the same idea but exposes it
through different APIs.

## The model

- **One run = one trace.** Each `agent.run()` /
  `crew.kickoff()` / chat completion / agent loop iteration
  = one trace.
- **A session groups the runs of one conversation.** Reuse
  the same `session_id` on every run.
- **End-user is per session.** Same `end_user_id` for all
  runs of one conversation. Different `end_user_id` for
  different customers.
- **Identity is root-only.** You set it once on the trace
  root; the backend rolls it up. Do NOT tag individual child
  spans.
- `init()` takes **no** session / end-user params.
  `init()`'s `user_id` (if used) is the SDK operator (you),
  not your app's end-user.

## OpenLLMetry / OpenTelemetry → NeatLogs mapping

| OTel / OpenLLMetry (v0.x) | NeatLogs |
|---|---|
| `OTEL_RESOURCE_ATTRIBUTES="session.id=...;enduser.id=..."` (env) | `with neatlogs.identify(session_id=..., end_user_id=...):` around the call |
| `Resource(attributes={"session.id": "...", "enduser.id": "..."})` (code) | `with neatlogs.identify(session_id=..., end_user_id=...):` at the call site |
| `span.set_attribute("openinference.session.id", "...")` (OpenInference convention) | `with neatlogs.identify(session_id=...)` |
| `span.set_attribute("openinference.user.id", "...")` | `with neatlogs.identify(end_user_id=...)` |
| `span.set_attribute("openinference.conversation.id", "...")` (some libs) | `with neatlogs.identify(session_id=...)` |
| `tracer.start_as_current_span("...", attributes={"openinference.evaluation.user_score": 0.9})` | `span.set_attribute("neatlogs.user.score", 0.9)` |
| Resource attribute `service.name` (OTel) | Maps to NeatLogs `workflow_name` (set in step 3 of the migration) |
| `tracer_provider.force_flush()` | `neatlogs.flush()` |
| `tracer_provider.shutdown()` | `neatlogs.shutdown()` |

Note: OTel resource attributes are inherited by every span
in a trace, while NeatLogs' `identify()` block sets identity
for the active span and its children. The semantic is the
same; the API is different.

## How — wrapper-only (the common case)

The project already calls `neatlogs.wrap(...)` (step 3 added
`init()`; if it also wraps the LLM client, the wrapped call's
auto-root inherits identity via `identify()`):

```python
import neatlogs
from openai import OpenAI

neatlogs.init(api_key=..., workflow_name="...")
client = neatlogs.wrap(OpenAI())

# One conversation = one sessionId + end-user, reused across every turn.
SESSION = "conv_123"
USER = "u_456"

async def chat_turn(message: str) -> str:
    with neatlogs.identify(
        session_id=SESSION,
        end_user_id=USER,
        end_user_metadata={"plan": "pro"},
    ):
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": message}],
        )
    return resp.choices[0].message.content
```

Each `chat_turn` is one trace; all traces in the conversation
share `session_id="conv_123"` and `end_user_id="u_456"`, so
the backend groups them into one session for that customer.

## How — when the project opens its own root

If the project uses `@neatlogs.span(kind="WORKFLOW")` or
`with neatlogs.trace(...)` at the top of the call (i.e. not
wrapper-only), set identity on the root directly:

```python
@neatlogs.span(
    kind="WORKFLOW",
    session_id="conv_123",
    end_user_id="u_456",
    end_user_metadata={"plan": "pro"},
)
def handle_turn(message: str) -> str:
    ...
```

## OpenLLMetry-specific note

If the project was using OTel resource attributes for
identity (the most common OpenLLMetry pattern), the
attributes were set on the tracer provider once at process
start. After the migration, `neatlogs.identify()` is
scoped to a single call. If the project needs identity to
persist across many calls, wrap the call site with
`with neatlogs.identify(...)` rather than relying on
auto-inheritance.

If the project was using OpenInference conventions
(`openinference.session.id`, `openinference.user.id`),
these can stay as plain span attributes; the NeatLogs
backend doesn't read them. Identity is set via
`neatlogs.identify()`.

## Lineage (multi-session conversations)

`parent_session_id` groups a session under a parent. Useful
for "this conversation is a sub-thread of another":

```python
with neatlogs.identify(
    session_id="child_123",
    parent_session_id="parent_456",
    end_user_id="u_456",
):
    run_turn()
```

Application-specific session data (entry point, feature name,
tenant) goes in `session_custom_fields={...}`. Do NOT invent
fixed SDK parameters for individual custom keys.

## Dashboard

Filter traces by **End-user** or **Session** in the NeatLogs
dashboard. `end_user_metadata` keys (e.g. `plan=pro`) are
filterable too. The OTel / OpenLLMetry equivalents
(`session.id`, `enduser.id` resource attributes) are NOT
recognized by the NeatLogs dashboard as identity columns —
they're stored as plain attributes. The NeatLogs dashboard
rolls up identity server-side from the per-trace attributes
set by `neatlogs.identify()`.
