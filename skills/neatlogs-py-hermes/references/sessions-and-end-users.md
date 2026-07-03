# Sessions & end-users

## Why
Group a conversation's runs and attribute them to the customer's END-user (not the
SDK operator), so the dashboard can answer "what did user u_456 do?" and "show me
this whole conversation" — the basis for per-customer analytics and support.

## The model
- **One `agent.run(...)` = one trace.** A **session** groups the traces of a single
  conversation: every run in that conversation shares the SAME `session_id`.
- **End-user is per session** — one `end_user_id` (the customer's user) identifies who
  the conversation is with.
- **Root-only.** You attach identity at the trace root; the backend rolls the runs up
  into a session. You do NOT tag individual child spans.
- `init()` has NO session/end-user params. `user_id` at init is the *operator* (you),
  not your customer's user — leave it for that.

## How — WRAPPER-ONLY `identify()`
The hermes wrapper opens its own root (`AGENT hermes.run_conversation`), so use the
`identify()` context manager: wrap each `agent.run(...)` and the root inherits
`session_id` + end-user via the span processor (needs **neatlogs>=1.4.2**).

```python
import neatlogs

neatlogs.init(instrumentations=["hermes"])   # no session/end_user here
from run_agent import AIAgent

agent = neatlogs.wrap(AIAgent(model="openai/gpt-4o-mini", api_key=...))

# One conversation with customer u_456 — same session_id across turns.
with neatlogs.identify(
    session_id="conv_123",
    end_user_id="u_456",
    end_user_metadata={"plan": "pro"},
):
    a1 = agent.run("What's the status of my order?")     # trace 1
    a2 = agent.run("Can you cancel the second item?")     # trace 2
    a3 = agent.run("Thanks — email me the refund total.") # trace 3
```

All three runs land under session `conv_123`, attributed to end-user `u_456`. A new
conversation uses a new `session_id`; the same customer keeps the same `end_user_id`.

- Wrap only the runs that belong to the conversation; each `identify()` block is one
  session. Don't nest sessions.
- Every run inside ONE conversation must reuse the SAME `session_id`.

## Dashboard
Filter traces by `session_id` (view a whole conversation) or by `end_user_id`
(everything one customer did) in the Neatlogs UI.
