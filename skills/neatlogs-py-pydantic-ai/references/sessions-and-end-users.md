# Sessions & End-Users

Attach a **session** (a conversation) and an **end-user** (your customer's user) to traces so the Neatlogs dashboard can roll up analytics per conversation and per end-user — who is using the agent, how many turns each conversation ran, cost/latency per customer.

## The model

- **One run = one trace.** Each `agent.run_sync(...)` / `await agent.run(...)` produces one trace (the wrapper's AGENT root).
- **A session groups the runs of one conversation.** Give every turn of the same conversation the SAME `session_id`.
- **End-user is per session.** Set `end_user_id` (and optional `end_user_metadata`) alongside the session id.
- **Root-only.** You attach identity once at the top; the backend rolls it up. Do NOT tag child spans.

## API — wrapper-only `identify()`

`neatlogs.wrap()` opens its own AGENT root, so `init()` takes NO session/end-user params (its `user_id` is the *operator* running the SDK, not your customer). Instead wrap each turn in `neatlogs.identify(...)`; the agent's root inherits the session + end-user via the span processor (needs `neatlogs>=1.4.2`).

```python
with neatlogs.identify(session_id="conv_123", end_user_id="u_456",
                       end_user_metadata={"plan": "pro"}):
    result = agent.run_sync(message)
```

## Multi-turn conversation

Reuse the same `session_id` + `end_user_id` for every turn of one conversation:

```python
import neatlogs
from .agent import chat_agent

agent = neatlogs.wrap(chat_agent)

def handle_conversation(session_id: str, user_id: str, turns: list[str]):
    for message in turns:
        with neatlogs.identify(session_id=session_id, end_user_id=user_id,
                               end_user_metadata={"plan": "pro"}):
            result = agent.run_sync(message)          # one trace per turn
            print(result.output)

handle_conversation("conv_123", "u_456",
                    ["Hi, what can you do?", "Summarize my last invoice", "Thanks!"])
```

The three `run_sync` calls become three traces that the dashboard groups under session `conv_123`, all attributed to end-user `u_456`.

## Dashboard

Filter or group by `session_id` / `end_user_id` in the Neatlogs dashboard to view a whole conversation or all activity for one customer.
