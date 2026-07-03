# Sessions & end-users

Attach *who* (the customer's end-user) and *which conversation* (the session) to Strands
traces, so the dashboard can group turns and slice analytics per user — not the SDK operator.

## The model

- **One turn = one trace.** Each `agent(message)` call opens its own Strands root trace.
- **A session groups the turns of one conversation** — pass the SAME `session_id` for every
  turn of that conversation.
- **End-user is per session** — `end_user_id` (+ optional `end_user_metadata`) identifies the
  customer's user. Root-only; the backend rolls turns up under the session/user.
- `init()` has NO session/end-user params (`user_id` there is the *operator*, not the customer).
  Identity is per-turn via the **wrapper-only** `neatlogs.identify(...)` context manager.

Strands self-instruments and opens its own root. `neatlogs.identify(...)` writes session +
end-user onto that native root via the span processor (requires **neatlogs>=1.4.2**).

## Multi-turn example

Wrap each `agent(message)` in `identify()` with the same `session_id` + `end_user_id`:

```python
import neatlogs
neatlogs.init(api_key=os.getenv("NEATLOGS_API_KEY"), workflow_name="support-bot")

from strands import Agent
agent = neatlogs.strands_hooks(Agent(model=model, tools=[...]))

session_id = "conv_123"          # stable for this whole conversation
end_user_id = "u_456"            # the customer's end-user

for message in conversation_turns:            # each turn = its own trace
    with neatlogs.identify(
        session_id=session_id,
        end_user_id=end_user_id,
        end_user_metadata={"plan": "pro"},
    ):
        reply = str(agent(message))           # Strands root inherits session + end-user
```

Every turn is a separate trace, but all share `conv_123` / `u_456`, so the backend groups
them under one session for that user.

## Dashboard

Filter traces by session or end-user in the dashboard to see one conversation end-to-end or
everything a given customer's user did.
