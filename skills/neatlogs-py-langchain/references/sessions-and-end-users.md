# Sessions & End-Users

## Why

Attach a **session** and an **end-user** to your traces so the Neatlogs dashboard can answer customer-analytics questions: usage / cost / errors per end-user and per segment (e.g. plan tier), multi-turn conversation timelines grouped as one session, and per-customer replay. Without this, every turn is an anonymous, standalone trace and none of it rolls up to a customer.

The `user_id` on `init()` is the **operator** (you / your service) — it is NOT the end-user. End-user identity is bound per turn, at call time.

## The model

- **One turn = one trace.** A single `.invoke()` / `.ainvoke()` produces one trace.
- **A session groups the turns of a conversation.** Use the SAME `session_id` on every turn of the same conversation.
- **End-user is per session.** Pass the same `end_user_id` (and any `end_user_metadata`) on each turn.
- **Root-only.** You bind identity once at the top of the turn; the LangChain root and every span under it inherit it. The backend rolls the turns up into the session and the end-user. Requires `neatlogs>=1.4.2`.

## How — wrapper-only `identify()`

This skill instruments LangChain via the callback handler (LangChain opens its own trace root). Bind identity by wrapping the invoke in `neatlogs.identify()`:

```python
with neatlogs.identify(session_id="conv_123", end_user_id="u_456", end_user_metadata={"plan": "pro"}):
    llm.invoke(message, config={"callbacks": [handler]})   # or chain.invoke(...)
```

`init()` takes NO session / end_user params — identity is per-call only, via `identify()`.

## Realistic multi-turn example

Same `session_id` + `end_user_id` on every turn of the conversation:

```python
import neatlogs
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

neatlogs.init(api_key=os.getenv("NEATLOGS_API_KEY"))   # operator only; no session/end_user here
handler = neatlogs.langchain_handler()
llm = ChatOpenAI(model="gpt-4o")

SESSION = "conv_123"          # one conversation
END_USER = "u_456"            # the customer's end-user
META = {"plan": "pro"}

# turn 1
with neatlogs.identify(session_id=SESSION, end_user_id=END_USER, end_user_metadata=META):
    r1 = llm.invoke([HumanMessage("What's my current plan?")], config={"callbacks": [handler]})

# turn 2 — SAME session_id + end_user_id → grouped into the same session
with neatlogs.identify(session_id=SESSION, end_user_id=END_USER, end_user_metadata=META):
    r2 = llm.invoke(
        [HumanMessage("What's my current plan?"), r1, HumanMessage("Can I upgrade?")],
        config={"callbacks": [handler]},
    )
```

Each turn is its own trace; both share `conv_123`, so the dashboard shows them as one multi-turn session for end-user `u_456`.

## Dashboard filter

In the Neatlogs dashboard, filter by `end_user_id` (or `session_id`) to see all traces, cost, and errors for a single customer or conversation.
