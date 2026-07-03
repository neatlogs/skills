# Sessions & End-Users

## Why

Attach a **session** and an **end-user** to your crew runs so the Neatlogs dashboard can roll up customer analytics: usage / cost / errors per end-user and per segment (e.g. plan tier), conversation timelines that group several runs, and per-customer replay. Without identity, every `kickoff()` is an anonymous trace and you can't answer "what did user u_456 do?" or "how much did the pro tier cost this week?".

## The model

- **One run = one trace.** Each `crew.kickoff()` produces one trace.
- **A session groups several runs of one conversation.** Pass the SAME `session_id` on every `kickoff()` that belongs to the same conversation.
- **End-user is per session.** The customer's end-user (NOT the SDK operator) is identified alongside the session.
- **Identity is root-only.** `wrap(crew)` opens its own root span (`crewai.crew.kickoff`); it inherits the session + end-user from the surrounding `identify()` via the span processor (**neatlogs >= 1.4.2**). The backend rolls the identity up the tree — you set it once, at the root, per run.

`init()` takes NO session / end-user params (its `user_id` is the operator running the SDK, not your customer). Identity is bound per run with `neatlogs.identify()`.

## How — wrap each run in `identify()`

Because `wrap(crew)` owns the root, use the WRAPPER-ONLY path: wrap each `kickoff()` in `neatlogs.identify()`.

```python
with neatlogs.identify(session_id="conv_123", end_user_id="u_456", end_user_metadata={"plan": "pro"}):
    result = crew.kickoff(inputs={"question": message})
```

The crew's root (`crewai.crew.kickoff`) inherits the session + end-user; all nested AGENT / TOOL / LLM spans roll up under it.

## Realistic example — a multi-turn conversation

Each turn is a separate `kickoff()`, so each is its own trace. Pass the SAME `session_id` and `end_user_id` every turn to group them into one conversation timeline:

```python
import neatlogs
from crewai import Crew, Process

neatlogs.init(api_key=os.getenv("NEATLOGS_API_KEY"))

crew = neatlogs.wrap(Crew(agents=[...], tasks=[...], process=Process.sequential))

session_id = "conv_123"          # one conversation
end_user = dict(end_user_id="u_456", end_user_metadata={"plan": "pro"})

for message in conversation_turns:          # each turn = one kickoff = one trace
    with neatlogs.identify(session_id=session_id, **end_user):
        result = crew.kickoff(inputs={"question": message})
        print(result)
```

## Dashboard

The runs now carry identity, so the Neatlogs dashboard **End-user** and **Session** filters let you scope traces, cost, and errors to a single customer or conversation.
