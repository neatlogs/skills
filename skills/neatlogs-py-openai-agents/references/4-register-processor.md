# Step 4: Register the Trace Processor

## Action

Register the neatlogs processor ONCE at startup — after `init()`, after importing `agents`, and before the first `Runner.run()`:

```python
import neatlogs
from agents import add_trace_processor

add_trace_processor(neatlogs.openai_agents_processor())
```

That single call wires the OpenAI Agents SDK's tracing protocol into neatlogs. Every agent run afterward (agents, tools, handoffs, guardrails, LLM calls) is captured — nothing per-agent to configure.

## Where to put it

Put it next to `init()` in the entry module, once:

```python
import os
import neatlogs
from dotenv import load_dotenv

load_dotenv()
neatlogs.init(api_key=os.getenv("NEATLOGS_API_KEY"), workflow_name="support-agents")

from agents import Agent, Runner, add_trace_processor
add_trace_processor(neatlogs.openai_agents_processor())   # once, before any Runner.run()

from src.agents.triage import triage_agent
```

- Register it **once** for the process. Do NOT call it inside a per-request handler or per-query loop — that stacks duplicate processors.
- It must run before the first `Runner.run()` / `Runner.run_sync()`; spans from runs that happen before registration are not captured.

## WRONG vs RIGHT

```python
# ❌ WRONG — processor never registered. The Agents SDK runs but nothing is traced.
result = await Runner.run(triage_agent, query)

# ❌ WRONG — registered inside the request handler → a new processor each call (duplicates).
async def handle(query):
    add_trace_processor(neatlogs.openai_agents_processor())   # moved this out to startup
    return await Runner.run(triage_agent, query)

# ✅ RIGHT — registered once at startup, before Runner.run().
add_trace_processor(neatlogs.openai_agents_processor())
result = await Runner.run(triage_agent, query)
```

## Verify BEFORE moving to step 5

1. Exactly ONE `add_trace_processor(neatlogs.openai_agents_processor())` call, at startup.
2. It runs after `init()` + the `agents` import, and before the first `Runner.run()`.
3. It is NOT inside a per-request / per-query function.
4. `import neatlogs` is present in that file.
