# Sessions & End-Users

## Why

`init()` only identifies the *operator* (your app, via `user_id`). To answer "which of MY customers' end-users are running these agents, and across which conversations?" you attach a **session** and an **end-user** to each run. The backend rolls these up so the dashboard can group turns into conversations and filter analytics per end-user.

## The Model

- **One turn = one trace.** Each `Runner.run_sync()` / `await Runner.run()` produces one WORKFLOW root.
- **A session groups turns.** Pass the **same `session_id`** on every turn of the same conversation.
- **End-user per session.** The person the turn is for — same `end_user_id` for their turns.
- **Root-only.** You bind identity on the run root; the backend rolls it up. Do NOT try to tag child agent/tool/LLM spans.

## Binding Identity — Wrapper-Only Path

`init()` takes NO session/end-user params. Bind per turn with `neatlogs.identify()` (requires `neatlogs>=1.4.2`) around the `Runner.run` call. The agent run's root inherits the session + end-user via the span processor:

```python
with neatlogs.identify(
    session_id="conv_123",
    end_user_id="u_456",
    end_user_metadata={"plan": "pro"},
):
    result = Runner.run_sync(agent, message)
```

## Realistic Multi-Turn Example

Same `session_id` + `end_user_id` across every turn of one conversation:

```python
import neatlogs
from agents import Agent, Runner, add_trace_processor

neatlogs.init(api_key=os.getenv("NEATLOGS_API_KEY"), user_id="support-bot")
add_trace_processor(neatlogs.openai_agents_processor())

agent = Agent(name="Support", instructions="Help the customer.")

@neatlogs.span(kind="WORKFLOW", name="support_conversation")
def handle_conversation(session_id: str, end_user_id: str, turns: list[str]) -> None:
    for message in turns:
        # SAME session_id + end_user_id every turn → one grouped conversation
        with neatlogs.identify(
            session_id=session_id,
            end_user_id=end_user_id,
            end_user_metadata={"plan": "pro"},
        ):
            result = Runner.run_sync(agent, message)
            print(result.final_output)

handle_conversation(
    session_id="conv_2026_07_02_alice",
    end_user_id="u_alice",
    turns=["Where's my order?", "Can I change the address?"],
)
```

Each turn is its own trace; all three share `session_id="conv_2026_07_02_alice"`, so the dashboard shows them as one conversation for end-user `u_alice`.

## Dashboard

Filter traces by session or end-user in the Neatlogs dashboard to view a full conversation or every run belonging to one customer's end-user.
