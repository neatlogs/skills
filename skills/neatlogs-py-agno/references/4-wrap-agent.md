# Step 4: Wrap the Agent with neatlogs.wrap()

```python
import neatlogs
from .assistant import support_agent

agent = neatlogs.wrap(support_agent)

resp = agent.run("What is the status of order ORD-001?")
print(resp.content)
```

Produces:
```
AGENT  agno.agent.run
  ↳ LLM   agno.model.invoke
  ↳ TOOL  agno.tool.<name>
```

Works for `Team` and `Workflow` too (TEAM / WORKFLOW span). Streaming (`run(stream=True)` / `arun`) is supported — the span stays active across the stream.

## Rules
- Wrap each entity once; use the returned reference.
- Do NOT wrap a single `agent.run()` in `@span`/`trace`.
