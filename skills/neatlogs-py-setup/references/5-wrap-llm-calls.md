# Step 5: Wrap LLM Calls with trace() and Prompt Templates

## Action

Find EVERY function that contains a direct LLM API call and wrap it with `neatlogs.trace()` + prompt templates. This applies to ALL functions with LLM calls — whether or not they have `@span`.

## How to Find LLM Calls

Refer to `references/llm-call-patterns.md` for the complete list. Key patterns:

| Library | Call pattern |
|---------|-------------|
| OpenAI | `client.chat.completions.create(...)` |
| Anthropic | `client.messages.create(...)` |
| Google GenAI | `client.models.generate_content(...)` |
| LangChain | `llm.invoke(...)`, `llm.ainvoke(...)`, `llm_with_tools.invoke(...)` |
| Groq | `client.chat.completions.create(...)` |
| Bedrock | `client.converse(...)` |
| LiteLLM | `litellm.completion(...)` |

## Why This Applies Even Inside Auto-Instrumented Code

The auto-instrumentor (e.g., `"langchain"`) captures call metadata (model, tokens, latency) automatically. But it does NOT capture **prompt template structure** — which variables go into which positions. That's what `neatlogs.trace()` + `SystemPromptTemplate`/`UserPromptTemplate` provides. Without templates, prompts don't appear in the Neatlogs prompt management dashboard.

So even inside a LangChain node function like this:

```python
def analyst_node(state: AgentState) -> dict:
    messages = [SystemMessage(content=SYSTEM_PROMPT), *state["messages"]]
    response = llm_with_tools.invoke(messages)  # ← LLM call! Needs trace + templates
    return {"messages": [response]}
```

You MUST wrap the LLM call.

## Full Pattern (always follow this)

```python
from neatlogs import SystemPromptTemplate, UserPromptTemplate

# Define templates at MODULE LEVEL (outside functions)
SUMMARIZE_SYS_TPL = SystemPromptTemplate([
    {"role": "system", "content": "You are a document summarizer. Keep under {{max_words}} words."}
])
SUMMARIZE_USER_TPL = UserPromptTemplate([
    {"role": "user", "content": "Summarize the following text:\n\n{{text}}"}
])


@neatlogs.span(kind="CHAIN")
async def summarize(text: str, settings: Settings) -> str:
    client = AsyncOpenAI(api_key=settings.api_key)
    with neatlogs.trace("llm_call", kind="LLM",
                        system_prompt_template=SUMMARIZE_SYS_TPL,
                        user_prompt_template=SUMMARIZE_USER_TPL):
        msgs = SUMMARIZE_SYS_TPL.compile(max_words="200") + SUMMARIZE_USER_TPL.compile(text=text)
        response = await client.chat.completions.create(
            model=settings.model_name,
            messages=msgs,
        )
    return response.choices[0].message.content.strip()
```

## LangChain Pattern — llm.invoke() with templates

When the LLM call uses LangChain's `.invoke()`, you MUST still create `SystemPromptTemplate` and `UserPromptTemplate` objects. Do NOT pass raw strings.

### WRONG vs RIGHT

```python
# ❌ WRONG — passing raw strings. Templates won't appear in dashboard.
ANALYST_SYSTEM_PROMPT = "You are a senior business analyst..."

def analyst_node(state: AgentState) -> dict:
    with neatlogs.trace("analyst_llm", kind="LLM",
                        system_prompt_template=ANALYST_SYSTEM_PROMPT,  # RAW STRING = BROKEN
                        user_prompt_template=str(state["messages"][-1].content)):  # RAW STRING = BROKEN
        response = llm_with_tools.invoke(messages)
    return {"messages": [response]}

# ✅ RIGHT — using SystemPromptTemplate/UserPromptTemplate objects
from neatlogs import SystemPromptTemplate, UserPromptTemplate

ANALYST_SYS_TPL = SystemPromptTemplate([
    {"role": "system", "content": "You are a senior business analyst with expertise in data analysis."}
])
ANALYST_USER_TPL = UserPromptTemplate([
    {"role": "user", "content": "{{user_query}}"}
])


def analyst_node(state: AgentState) -> dict:
    messages = state["messages"]
    system_msg = SystemMessage(content=ANALYST_SYSTEM_PROMPT)

    with neatlogs.trace("analyst_llm", kind="LLM",
                        system_prompt_template=ANALYST_SYS_TPL,
                        user_prompt_template=ANALYST_USER_TPL):
        response = llm_with_tools.invoke([system_msg] + list(messages))

    return {"messages": [response]}
```

### Key rules for LangChain trace():
- You MUST use `SystemPromptTemplate([...])` and `UserPromptTemplate([...])` objects, never raw strings
- Define templates at **module level** (not inside functions)
- For LangChain `.invoke()`, you don't use `.compile()` to build messages — LangChain uses its own message classes
- The templates are for Neatlogs to track what prompt structure was used for the dashboard
- If a system prompt is a string constant (e.g., `ANALYST_SYSTEM_PROMPT`), wrap it: `SystemPromptTemplate([{"role": "system", "content": "...the value..."}])`

## How to Convert Existing Prompts to Templates

Any prompt that contains a variable (f-string, .format(), concatenation) becomes a template:

| Before | After |
|--------|-------|
| `f"Summarize: {text}"` | `UserPromptTemplate([{"role": "user", "content": "Summarize: {{text}}"}])` |
| `f"You are a {role} assistant"` | `SystemPromptTemplate([{"role": "system", "content": "You are a {{role}} assistant"}])` |
| `"Extract entities from the text."` (static) | `SystemPromptTemplate([{"role": "system", "content": "Extract entities from the text."}])` |
| `SYSTEM_PROMPT` (constant string) | `SystemPromptTemplate([{"role": "system", "content": "...the constant value..."}])` |

Even static prompts get templates — this makes them visible in the Neatlogs dashboard for prompt management.

## Template Rules

- Templates use `{{double_braces}}` for variables
- `.compile(var=value)` renders and returns a `list[dict]` ready for `messages=`
- Combine system + user: `msgs = sys_tpl.compile(...) + user_tpl.compile(...)`
- Define at **module level**, not inside functions
- Import: `from neatlogs import SystemPromptTemplate, UserPromptTemplate`
- Name convention: `UPPERCASE_DESCRIPTIVE_TPL` (e.g., `EXTRACT_SYS_TPL`, `COMBINE_USER_TPL`)

## Multiple LLM Calls in One Function

If a function makes multiple LLM calls, wrap each one in its own `trace()` with its own templates:

```python
@neatlogs.span(kind="AGENT")
async def research_agent(topic):
    with neatlogs.trace("search_call", kind="LLM",
                        system_prompt_template=SEARCH_SYS_TPL,
                        user_prompt_template=SEARCH_USER_TPL):
        msgs = SEARCH_SYS_TPL.compile() + SEARCH_USER_TPL.compile(topic=topic)
        search_result = await client.chat.completions.create(messages=msgs, ...)

    with neatlogs.trace("synthesis_call", kind="LLM",
                        system_prompt_template=SYNTH_SYS_TPL,
                        user_prompt_template=SYNTH_USER_TPL):
        msgs = SYNTH_SYS_TPL.compile() + SYNTH_USER_TPL.compile(context=search_result)
        final = await client.chat.completions.create(messages=msgs, ...)
    return final
```

## Verification Checklist

- [ ] Every function with an LLM call (see patterns above) has `with neatlogs.trace(...)` around the call
- [ ] This includes LangChain `.invoke()` / `.ainvoke()` calls inside graph nodes
- [ ] Every `trace()` has both `system_prompt_template=` and `user_prompt_template=` parameters
- [ ] Templates are defined at module level with `UPPERCASE_TPL` naming
- [ ] Template variables use `{{double_braces}}`
- [ ] `from neatlogs import SystemPromptTemplate, UserPromptTemplate` is in each file that uses them
