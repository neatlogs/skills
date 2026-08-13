# Sessions & end-users

Lineage is modeled with `parent_session_id`. Application-specific session data is
not hardcoded into SDK parameters: pass any JSON-compatible keys through
`session_custom_fields={...}`. The SDK stores that object as
`neatlogs.session.custom_fields` on the root span. For example:

```python
with neatlogs.identify(
    session_id="child_123",
    parent_session_id="parent_456",
    session_custom_fields={"feature_name": "chat", "entry_point": "slack", "tenant": "acme"},
    end_user_id="u_456",
):
    run_turn()
```


Attaching a session + end-user to a turn's trace turns raw traces into customer analytics: usage / cost / errors per user and segment, multi-turn conversation timelines, and per-customer replay. Without it, traces are anonymous and can't be rolled up by who caused them.

## Model

- One `agent.run(...)` / `agent.arun(...)` = one trace.
- A **session** groups the runs of one conversation — pass the SAME `session_id` on every turn.
- An **end-user** is per session — pass the SAME `end_user_id` (this is YOUR app's user, not the operator).
- Identity is **root-only**: `wrap()` opens the trace root, and the span processor attaches session + end-user there (neatlogs>=1.4.2). Backend rolls it up; child spans ignore it.

`init()` has NO session/end_user params (its `user_id` is the operator running the SDK, not your app's user). Because the wrapper owns the root, use **wrapper-only** `neatlogs.identify()` per turn.

## Per turn

```python
with neatlogs.identify(session_id="conv_123", end_user_id="u_456", end_user_metadata={"plan": "pro"}):
    agent.run(message)
```

The wrapped agent's root inherits the session and end-user automatically.

## Multi-turn conversation

Same `session_id` + `end_user_id` on every turn ties the runs into one timeline for that customer:

```python
import neatlogs

agent = neatlogs.wrap(support_agent)

SESSION_ID = "conv_123"
END_USER   = "u_456"

conversation = [
    "What is the status of order ORD-001?",
    "Can I still change the shipping address?",
    "Great, cancel the second item then.",
]

for message in conversation:
    with neatlogs.identify(session_id=SESSION_ID, end_user_id=END_USER, end_user_metadata={"plan": "pro"}):
        resp = agent.run(message)     # this turn's trace carries session + end-user
        print(resp.content)
```

Works the same for `arun` and for wrapped `Team` / `Workflow`.

## Dashboard

Traces are filterable by **End-user** and **Session** in the Neatlogs dashboard — pivot to a single customer or a single conversation.
