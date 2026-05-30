# Step 5: Attach Prompt Templates (Optional, for Prompt Management)

CrewAI owns the LLM calls internally, so you CANNOT wrap them in `neatlogs.trace()` like direct-SDK code. Instead, the SDK provides two CrewAI-specific APIs to attach prompt context:

- `neatlogs.bind_templates(llm, system_tpl)` → attaches a system template to an Agent's LLM
- `neatlogs.register_crewai_task(task, user_tpl, **vars)` → attaches a user template to a Task

This step is OPTIONAL — skip it if the project doesn't need prompt versioning/management in the dashboard. Tracing of agents/tasks/tools/LLM works without it.

## bind_templates() — Agent system prompts

```python
import neatlogs
from neatlogs import SystemPromptTemplate
from crewai import Agent, LLM

# System template must NOT have required placeholders — bind_templates() calls
# system_tpl.compile() with no arguments. Pre-render any variables.
ANALYST_TPL = SystemPromptTemplate("You are a senior market analyst for the tech industry.")

llm = LLM(model="gpt-4o")
bound_llm = neatlogs.bind_templates(llm, ANALYST_TPL)   # returns a NEW LLM instance

analyst = Agent(
    role="Market Analyst",
    goal="Provide market analysis",
    backstory="...",
    llm=bound_llm,        # use the bound LLM
)
```

## register_crewai_task() — Task user prompts

COMPILE the task template and use its output as the Task `description`, THEN register the same template + variables. The description the crew actually runs and the tracked template must be the same compiled string — do not hardcode a separate `description`.

```python
from neatlogs import UserPromptTemplate

# Define as a STRING template → compile() returns a str (Task.description is a string)
TASK_TPL = UserPromptTemplate("Analyze {{topic}} trends for {{year}}.")

task = Task(
    description=TASK_TPL.compile(topic="AI chips", year="2025"),  # ← compiled output IS the description
    expected_output="Market analysis report",
    agent=analyst,
)
neatlogs.register_crewai_task(task, TASK_TPL, topic="AI chips", year="2025")
```

```python
# ❌ WRONG — description hardcoded; TASK_TPL registered separately. The tracked template
# is disconnected from what the task actually runs.
task = Task(description="Analyze AI chip market trends", agent=analyst)
neatlogs.register_crewai_task(task, TASK_TPL, topic="AI chips", year="2025")
```

## Rules

- `{{variables}}` are for genuinely dynamic data, NEVER for a whole authored prompt. If an agent's backstory/goal or a task description is SELECTED from a fixed set of constants at runtime, make one template per constant (real text baked in) and pick by key — do not collapse into a single `{{prompt}}` passthrough (the dashboard would show `{{prompt}}` instead of the wording).
- Define templates at MODULE level with `UPPERCASE_TPL` naming.
- `SystemPromptTemplate` used with `bind_templates()` must have NO required `{{placeholders}}` (it is compiled with no args). Put variables in the `UserPromptTemplate` / `register_crewai_task(**vars)` instead.
- `bind_templates()` returns a NEW LLM — you must pass the returned `bound_llm` to the Agent, not the original.
- Import `from neatlogs import SystemPromptTemplate, UserPromptTemplate` where templates are defined; `import neatlogs` where `bind_templates`/`register_crewai_task` are called.
- Do NOT wrap CrewAI LLM calls in `neatlogs.trace()` — it won't work (the framework owns the call).

## WRONG vs RIGHT

```python
# ❌ WRONG — trying to wrap a crew/agent LLM call in trace(). CrewAI owns the call.
with neatlogs.trace("agent_llm", kind="LLM", system_prompt_template=TPL):
    result = crew.kickoff()

# ❌ WRONG — system template with a required placeholder used in bind_templates()
ANALYST_TPL = SystemPromptTemplate("You are a {{role}} analyst.")   # compile() will fail
bound = neatlogs.bind_templates(llm, ANALYST_TPL)

# ✅ RIGHT — bind a placeholder-free system template; variables go on the task template
ANALYST_TPL = SystemPromptTemplate("You are a senior market analyst.")
bound = neatlogs.bind_templates(llm, ANALYST_TPL)
TASK_TPL = UserPromptTemplate("Analyze {{topic}}.")
neatlogs.register_crewai_task(task, TASK_TPL, topic="AI chips")
```

## Verification

- [ ] If templates are used: agents use the `bound_llm` returned by `bind_templates()`, not the raw LLM.
- [ ] System templates passed to `bind_templates()` have no required placeholders.
- [ ] For tasks: `Task(description=TASK_TPL.compile(**vars))` — the compiled template IS the description, registered with the same vars via `register_crewai_task`. No hardcoded description disconnected from the registered template.
- [ ] No `neatlogs.trace()` wraps any CrewAI call.
