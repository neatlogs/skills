# Step 4: Wrap the Agent with neatlogs.wrap()

Wrap each Pydantic AI `Agent` instance. `wrap()` patches run/run_sync/run_stream/iter and installs class-level Model (LLM) + tool (TOOL) hooks. It returns the same instance.

```python
import neatlogs
from .agent import research_agent

agent = neatlogs.wrap(research_agent)

result = agent.run_sync("What is observability?")
print(result.output)
```

This produces:
```
AGENT  pydantic_ai.agent.run_sync
  ↳ LLM   pydantic_ai.model.request   (per model call)
  ↳ TOOL  pydantic_ai.tool.<name>     (per tool call)
```

## Rules
- Wrap the agent ONCE; use the returned reference for the actual calls.
- Do NOT wrap a single `agent.run()` in `@span`/`trace` — `wrap()` already opens the AGENT span.
- If the app defines multiple agents, wrap each one you want traced.
