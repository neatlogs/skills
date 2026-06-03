# Step 6: Wrap LLM Calls with trace() and Prompt Templates

## Action

Find EVERY graph node function that contains an LLM call (`llm.invoke()`, `llm.ainvoke()`, `llm_with_tools.invoke()`, etc.) and wrap the call with `neatlogs.trace()` + prompt templates.

## Why This Is Needed Even With the Handler

The handler captures: model name, token counts, latency, finish reason.
It does NOT capture: **prompt template structure** — which variables go into which positions.

Without `neatlogs.trace()` + `SystemPromptTemplate`/`UserPromptTemplate`, prompts don't appear in the Neatlogs prompt management dashboard. You cannot version, compare, or A/B test prompts without this.

## The core rule: COMPILE the templates and pass the result to `.invoke()`

A template is useless if it's only declared in `trace()` but the call sends something else — the dashboard would show a template disconnected from the real prompt. **You MUST `.compile()` the templates and feed the compiled output into `llm.invoke(...)`.** The tracked template and the invoked messages must be the SAME object.

`.compile()` returns a `list[dict]` of `{"role", "content"}` — which `ChatOpenAI`/`ChatAnthropic` `.invoke()` accepts directly. Use `sys.compile() + user.compile(**vars)`.

## Pattern — LangChain Node with LLM Call

```python
from neatlogs import SystemPromptTemplate, UserPromptTemplate

# Define templates at MODULE LEVEL (outside functions)
ANALYST_SYS_TPL = SystemPromptTemplate([
    {"role": "system", "content": "You are a senior business analyst with expertise in data analysis."}
])
ANALYST_USER_TPL = UserPromptTemplate([
    {"role": "user", "content": "{{user_query}}"}
])


def analyst_node(state: AgentState) -> dict:
    user_query = next(
        (m.content for m in reversed(state["messages"]) if getattr(m, "type", "") == "human"),
        "",
    )

    with neatlogs.trace("analyst_llm", kind="LLM",
                        system_prompt_template=ANALYST_SYS_TPL,
                        user_prompt_template=ANALYST_USER_TPL):
        # compile() → list[dict]; feed it straight into invoke()
        msgs = ANALYST_SYS_TPL.compile() + ANALYST_USER_TPL.compile(user_query=user_query)
        response = llm_with_tools.invoke(msgs)

    return {"messages": [response]}
```

> If the node must also pass prior conversation turns (`state["messages"]`), append them: `llm.invoke(ANALYST_SYS_TPL.compile() + list(state["messages"]))`. The point is the compiled template IS part of what's invoked — not a separate hand-built `SystemMessage` that bypasses the template.

## WRONG vs RIGHT

```python
# ❌ WRONG — passing raw strings. Templates won't appear in dashboard.
ANALYST_SYSTEM_PROMPT = "You are a senior business analyst..."

def analyst_node(state: AgentState) -> dict:
    with neatlogs.trace("analyst_llm", kind="LLM",
                        system_prompt_template=ANALYST_SYSTEM_PROMPT,        # RAW STRING = BROKEN
                        user_prompt_template=str(state["messages"][-1].content)):  # RAW STRING = BROKEN
        response = llm_with_tools.invoke(messages)
    return {"messages": [response]}
```

```python
# ❌ ALSO WRONG — templates declared in trace() but NEVER compiled/used.
# The call sends a hand-built SystemMessage, so the tracked template is decorative
# and disconnected from the real prompt.
def analyst_node(state: AgentState) -> dict:
    with neatlogs.trace("analyst_llm", kind="LLM",
                        system_prompt_template=ANALYST_SYS_TPL,
                        user_prompt_template=ANALYST_USER_TPL):
        response = llm_with_tools.invoke([SystemMessage(content="...")] + list(state["messages"]))  # template ignored
    return {"messages": [response]}

# ✅ RIGHT — compile the templates and invoke the compiled output
from neatlogs import SystemPromptTemplate, UserPromptTemplate

ANALYST_SYS_TPL = SystemPromptTemplate([
    {"role": "system", "content": "You are a senior business analyst with expertise in data analysis."}
])
ANALYST_USER_TPL = UserPromptTemplate([
    {"role": "user", "content": "{{user_query}}"}
])


def analyst_node(state: AgentState) -> dict:
    user_query = next(
        (m.content for m in reversed(state["messages"]) if getattr(m, "type", "") == "human"),
        "",
    )
    with neatlogs.trace("analyst_llm", kind="LLM",
                        system_prompt_template=ANALYST_SYS_TPL,
                        user_prompt_template=ANALYST_USER_TPL):
        msgs = ANALYST_SYS_TPL.compile() + ANALYST_USER_TPL.compile(user_query=user_query)
        response = llm_with_tools.invoke(msgs)

    return {"messages": [response]}
```

## How to Find LLM Calls in LangChain/LangGraph Code

| Call pattern | Where it appears |
|-------------|-----------------|
| `llm.invoke(messages)` | Node functions with ChatOpenAI/ChatAnthropic |
| `llm.ainvoke(messages)` | Async node functions |
| `llm_with_tools.invoke(messages)` | Nodes with tool-bound LLMs |
| `llm_with_tools.ainvoke(messages)` | Async nodes with tool-bound LLMs |
| `llm.stream(messages)` | Streaming nodes |
| `llm.astream(messages)` | Async streaming nodes |

## How to Convert Existing Prompts to Templates

| Before (in the code) | Template |
|---------------------|----------|
| `SYSTEM_PROMPT = "You are a planner..."` (string constant) | `SystemPromptTemplate([{"role": "system", "content": "You are a planner..."}])` |
| `f"Analyze {query} with context"` (f-string) | `UserPromptTemplate([{"role": "user", "content": "Analyze {{query}} with context"}])` |
| `state["messages"][-1].content` (dynamic user input) | `UserPromptTemplate([{"role": "user", "content": "{{user_query}}"}])` |

## Template Rules

- `{{variables}}` are for genuinely dynamic data (user input, retrieved context, runtime values) — NEVER for a whole authored prompt. A template whose entire content is one variable (`{{system_prompt}}`) is a useless passthrough; the dashboard shows `{{system_prompt}}` instead of the real wording. If a node's system prompt is SELECTED from a fixed set of constants at runtime (intent dispatch), make ONE `SystemPromptTemplate` per constant (with the real text baked in) and pick by key — do not collapse them into a single `{{system_prompt}}` template.
- Templates use `{{double_braces}}` for variables
- Define at **module level**, not inside functions
- Import: `from neatlogs import SystemPromptTemplate, UserPromptTemplate`
- Name convention: `UPPERCASE_DESCRIPTIVE_TPL` (e.g., `PLANNER_SYS_TPL`, `ANALYST_USER_TPL`)
- For LangChain `.invoke()`, you MUST `.compile()` the templates and pass the result (`list[dict]` of `{role, content}`) into `invoke()`. `ChatOpenAI`/`ChatAnthropic` accept that shape directly. Do NOT declare a template and then invoke a separate hand-built message — the template must be what's actually sent.
- The templates are for Neatlogs to track prompt structure; they don't replace LangChain's message handling

## Multiple Nodes = Multiple Template Pairs

Each node with an LLM call gets its own template pair:

```python
# Module level
PLANNER_SYS_TPL = SystemPromptTemplate([
    {"role": "system", "content": "You are a data analysis planning specialist..."}
])
PLANNER_USER_TPL = UserPromptTemplate([
    {"role": "user", "content": "{{user_query}}"}
])

ANALYST_SYS_TPL = SystemPromptTemplate([
    {"role": "system", "content": "You are a senior business analyst..."}
])
ANALYST_USER_TPL = UserPromptTemplate([
    {"role": "user", "content": "{{user_query}}"}
])
```

## Important: Do NOT Add @span to the Node

The node function itself should NOT have `@neatlogs.span()`. The callback handler already traces it (it sees the node's LLM call). You are ONLY adding the `with neatlogs.trace()` context manager INSIDE the function body, around the LLM call.

```python
# ❌ WRONG — do NOT add @span to node functions
@neatlogs.span(kind="CHAIN")
def planner_node(state: AgentState) -> dict:
    with neatlogs.trace(...):
        response = llm.invoke(messages)
    return {"messages": [response]}

# ✅ RIGHT — no decorator on the node, only trace() inside
def planner_node(state: AgentState) -> dict:
    with neatlogs.trace("planner_llm", kind="LLM",
                        system_prompt_template=PLANNER_SYS_TPL,
                        user_prompt_template=PLANNER_USER_TPL):
        response = llm.invoke(messages)
    return {"messages": [response]}
```

## Verification Checklist

- [ ] Every node function with `llm.invoke()` / `llm_with_tools.invoke()` has `with neatlogs.trace(...)` around the call
- [ ] Every `trace()` has both `system_prompt_template=` and `user_prompt_template=` parameters
- [ ] **The templates are `.compile()`d and the compiled result is what's passed to `.invoke()`** — NOT declared in trace() while a separate hand-built message is invoked
- [ ] Templates use `SystemPromptTemplate([...])` and `UserPromptTemplate([...])` objects, NOT raw strings
- [ ] Templates are defined at module level with `UPPERCASE_TPL` naming
- [ ] Template variables use `{{double_braces}}` and are bound via `.compile(var=value)`
- [ ] `from neatlogs import SystemPromptTemplate, UserPromptTemplate` is in each file that uses them
- [ ] NO node functions have `@neatlogs.span()` decorator on the def line
