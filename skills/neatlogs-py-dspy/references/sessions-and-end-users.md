# Sessions & end-users

Attach identity to traces so the backend can roll up **customer analytics** — usage, cost, and errors per end-user and per segment (e.g. plan tier), conversation timelines, and replay. This is your *customers'* end-users, not the SDK operator (that's `user_id` on `init()`).

## Model

- One program run = one trace.
- A **session** groups the runs of one conversation — every run shares the SAME `session_id`.
- An **end-user** owns the session (`end_user_id`, plus optional `end_user_metadata`).
- Identity is attached **root-only**; the backend rolls it up across the trace.
- `init()` has NO session/end-user params — only `user_id` (the operator). Identity is per-turn.

## Wrapper-only `identify()`

`neatlogs.wrap()` opens its own root when the module is called, so use **`neatlogs.identify()`** as a context manager around the call. The module's root inherits the session + end-user via the span processor (requires **neatlogs>=1.4.2**).

```python
with neatlogs.identify(session_id="conv_123", end_user_id="u_456", end_user_metadata={"plan": "pro"}):
    result = program(question=message)   # program(...) / program.forward(...)
```

## Example — a multi-turn conversation

Each turn is its own program run (its own trace), but all share one `session_id` and `end_user_id`:

```python
import neatlogs

program = QAPipeline()
neatlogs.wrap(program)

session_id = "conv_123"
end_user = dict(end_user_id="u_456", end_user_metadata={"plan": "pro"})

for message in conversation:                 # several turns in one conversation
    with neatlogs.identify(session_id=session_id, **end_user):
        result = program(question=message)   # one trace per run, grouped by session_id
        print(result.answer)
```

Different conversation → new `session_id`. Different customer → new `end_user_id`.

## Dashboard

Filter traces by `session_id`, `end_user_id`, or `end_user_metadata` (e.g. `plan=pro`) to see per-user / per-segment usage, cost, and error timelines.
