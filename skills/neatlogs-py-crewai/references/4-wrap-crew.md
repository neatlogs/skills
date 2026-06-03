# Step 4: Wrap the Crew with neatlogs.wrap()

## Action

Find where the `Crew` (or `Flow`) is constructed and wrap it before `kickoff()` is called:

```python
from crewai import Crew, Process
import neatlogs

crew = Crew(agents=[...], tasks=[...], process=Process.sequential)
crew = neatlogs.wrap(crew)          # patches kickoff + agents/tasks + BaseTool.run + LLM.call
result = crew.kickoff()
```

`wrap()` returns the SAME instance (patched in place). This single call gives you the whole tree:

```
WORKFLOW  crew.kickoff()
  ↳ AGENT   each agent's task execution
  ↳ TOOL    BaseTool.run
  ↳ LLM     LLM.call
```

## Where the crew is built

- **Built inside an entry function** (the common case) → wrap right after construction, before kickoff:
  ```python
  def run_pipeline(topic: str) -> str:
      crew = build_crew(topic)
      crew = neatlogs.wrap(crew)
      return str(crew.kickoff())
  ```
- **Built by a factory** → wrap the returned crew at the call site, or wrap inside the factory before returning.
- **CrewAI `@CrewBase` class with a `@crew` method** → wrap the `Crew(...)` the `@crew` method returns:
  ```python
  @crew
  def crew(self) -> Crew:
      return neatlogs.wrap(Crew(agents=self.agents, tasks=self.tasks, process=Process.sequential))
  ```
- **Flow** (`class MyFlow(Flow)`) → wrap the flow instance: `flow = neatlogs.wrap(MyFlow())` then `flow.kickoff()`.

Wrapping is idempotent — wrapping twice is harmless. Wrap at least once, before kickoff.

## No provider instrumentor needed

Do NOT add `instrumentations=["crewai", "openai"]` (or any provider). `wrap()` patches `LLM.call` directly, so LLM spans appear regardless of the model backend (OpenAI, Anthropic, Gemini, Azure, local). Pairing a provider instrumentor would double-fire LLM spans.

## WRONG vs RIGHT

```python
# ❌ WRONG — crew built and kicked off but never wrapped. No spans.
crew = Crew(agents=[...], tasks=[...])
result = crew.kickoff()

# ✅ RIGHT
crew = Crew(agents=[...], tasks=[...])
crew = neatlogs.wrap(crew)
result = crew.kickoff()
```

## Verify BEFORE moving to step 5

1. Grep for `.kickoff(`. The crew/flow it's called on was passed through `neatlogs.wrap(...)` first.
2. `init()` has NO `instrumentations=` for CrewAI.
3. `import neatlogs` is present in the file that calls `neatlogs.wrap(...)`.
