# Sessions & End-Users — for the migration

## Why

Attaching a **session** and an **end-user** to traces turns raw
telemetry into customer analytics: usage / cost / errors per user
and per segment, multi-turn conversation timelines, and per-
customer replay. LangSmith calls this "session + user"; NeatLogs
calls it the same thing but exposes it through different APIs.

## The model

- **One run = one trace.** Each `agent.run()` / `crew.kickoff()` /
  chat completion / agent loop iteration = one trace.
- **A session groups the runs of one conversation.** Reuse the
  same `session_id` on every run.
- **End-user is per session.** Same `end_user_id` for all runs
  of one conversation. Different `end_user_id` for different
  customers.
- **Identity is root-only.** You set it once on the trace root;
  the backend rolls it up. Do NOT tag individual child spans.
- `init()` takes **no** session / end-user params. `init()`'s
  `user_id` (if used) is the SDK operator (you), not your app's
  end-user.

## LangSmith → NeatLogs mapping

| LangSmith (v0.x) | NeatLogs |
|---|---|
| `LANGSMITH_SESSION` / `LANGCHAIN_SESSION` env var (LangSmith v0.1) | `with neatlogs.identify(session_id=...)` around the call |
| `client.create_run(session_name=...)` (LangSmith v0.2+) | `with neatlogs.identify(session_id=...)` at the call site |
| `client.update_current_run(session_name=...)` | Same `identify()` block, called once per session |
| `RunTree(name="...", session_name=...)` | `with neatlogs.identify(session_id=..., end_user_id=...)` at the parent |
| `client.create_run(name="...", inputs={"user_id": "..."})` | `with neatlogs.identify(end_user_id=..., session_id=...)` around the call (set the user field on the trace root, not on inputs) |
| `client.create_feedback(run_id=..., key="...", score=...)` | `span.set_attribute("neatlogs.user.feedback.<key>", score)` |
| Trace metadata `metadata={"session": "...", "user": "..."}` | `neatlogs.identify(session_id=..., end_user_id=..., session_custom_fields={...})` |
| `client.flush()` | `neatlogs.flush()` |

Note: LangSmith supports **per-run** metadata (a `metadata` dict
on `RunTree` or `create_run`). NeatLogs has no per-span metadata
dict — only flat attributes. Map the keys you care about via
`span.set_attribute("langsmith.meta.<key>", value)`; do NOT
encode the whole dict as one JSON string (the backend won't
render it).

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
share `session_id="conv_123"` and `end_user_id="u_456"`, so the
backend groups them into one session for that customer.

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

## LangChain-specific session grouping

If the project uses LangChain with `langchain.observability`,
the callback automatically creates a "session" (LangChain's
parent run) for a chain execution. To replicate that grouping
in NeatLogs, set `session_id` on the outermost call:

```python
# In the entry function (e.g. a FastAPI route):
@neatlogs.span(kind="WORKFLOW", name="chat_turn")
async def chat_turn(session_id: str, end_user_id: str, message: str) -> str:
    with neatlogs.identify(session_id=session_id, end_user_id=end_user_id):
        # LangChain runs here; the @traceable-wrapped functions
        # produce their spans inside the identify() scope and
        # inherit the session_id via the active context.
        response = await chain.ainvoke({"input": message})
    return response
```

The session_id flows through to all child spans because the
NeatLogs span processor reads it from the active OTel context.

## Lineage (multi-session conversations)

`parent_session_id` groups a session under a parent. Useful for
"this conversation is a sub-thread of another":

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
filterable too. The LangSmith equivalents
(`projects/<project>/sessions/`) are NOT — those are
LangSmith-specific dashboard views. The NeatLogs dashboard
rolls up identity server-side from the per-trace attributes.
