# Step 4: Wrap the agent with strands_hooks() + run it

Wrap every `Agent` with `neatlogs.strands_hooks(...)` — this installs the hook that
copies Strands' prompt/response content (which it records as OTel span *events*) onto
the spans as input/output. Without it you get spans + tokens but EMPTY input/output.

```python
from strands import Agent, tool
from strands.models import BedrockModel

agent = neatlogs.strands_hooks(
    Agent(
        model=BedrockModel(model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0", region_name="us-west-2"),
        tools=[add, celsius_to_fahrenheit],
        system_prompt="You are a concise math assistant.",
    )
)

resp = agent("What is 21 + 21?")
```

Produces (Strands' native spans, enriched with I/O by the hook):
```
agent  invoke_agent           (input/output)
  ↳ llm   chat                (input messages / output, tokens)
  ↳ tool  execute_tool <name> (args / result)
```

## Rules
- `strands_hooks()` returns the SAME agent — use the returned reference (or call it in place); it's idempotent (the hook installs once globally).
- It does NOT create its own spans — Strands' native OTel is the source of truth; the hook only adds input/output content to those spans.
- Do NOT register additional OTel processors or pass `instrumentations=[...]` for Strands — that would duplicate spans.
