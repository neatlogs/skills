# Sessions & End-Users

## Why

Attaching a **session** (the conversation) and an **end-user** (your app's user)
to traces turns raw telemetry into customer analytics: slice usage, cost,
latency, and errors per user and segment; view a multi-turn conversation as one
timeline; and replay a specific customer's conversation when they reach out.

## The model

- **One turn = one trace.** A **session** groups the turns of a conversation —
  pass the SAME `session_id` on every turn.
- **End-user is per session** — the same `end_user_id` on every turn.
- Identity is stamped on the **trace ROOT only**; the backend rolls it up; child
  spans ignore these fields.
- `init()` does NOT accept `session_id` / `auto_session` / `end_user` params.
  Its `user_id` is the OPERATOR running the SDK (you / a service account), NOT
  your app's end-user.

## How to set it

**If your code opens the root** (a `@neatlogs.span(kind="WORKFLOW")` decorator or
a top-level `with neatlogs.trace(...)`) — the common case for this generic setup
— pass identity there:

```python
@neatlogs.span(
    kind="WORKFLOW",
    session_id="conv_123",              # same id every turn
    end_user_id="u_456",
    end_user_metadata={"plan": "pro"},  # arbitrary JSON
)
def handle_turn(message: str) -> str:
    ...

# or the context-manager form:
with neatlogs.trace("chat_turn", session_id="conv_123", end_user_id="u_456"):
    run_agent(message)
```

**If you only called `neatlogs.wrap(client)`** and open no root of your own, bind
identity for the turn with `identify()` — the wrapper's auto-root inherits it:

```python
with neatlogs.identify(session_id="conv_123", end_user_id="u_456", end_user_metadata={"plan": "pro"}):
    client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": message}])
```

## Multi-turn example

```python
SESSION_ID = f"conv_{conversation_id}"   # one id for the whole conversation

for message in conversation:
    with neatlogs.trace("chat_turn", session_id=SESSION_ID, end_user_id="u_456",
                        end_user_metadata={"plan": "pro"}):
        run_agent(message)
# → one trace per turn, all grouped under SESSION_ID, attributed to u_456
```

## Dashboard

Filter traces by **Session** to see a whole conversation, or by **End-user** to
see everything one customer's end-user did. `end_user_metadata` fields are
filterable too.
