# Step 6: Wrap LLM Calls with trace() and Prompt Templates

## Action

Find EVERY function that contains a direct LLM API call and wrap the call with `neatlogs.trace()` + prompt templates. This applies to ALL functions with LLM calls — whether or not they have `@span`.

## How to Find LLM Calls

See `references/llm-call-patterns.md` for the full list. Key patterns for direct SDK usage:

| Library | Call pattern |
|---------|-------------|
| OpenAI | `client.chat.completions.create(...)`, `client.responses.create(...)` |
| Anthropic | `client.messages.create(...)`, `client.messages.stream(...)` |
| Google GenAI | `client.models.generate_content(...)` |
| Groq | `client.chat.completions.create(...)` |
| Bedrock | `client.converse(...)`, `client.invoke_model(...)` |
| LiteLLM | `litellm.completion(...)`, `litellm.acompletion(...)` |
| Mistral | `client.chat.complete(...)` |
| Cohere | `client.chat(...)`, `client.v2.chat(...)` |

## Why This Is Needed Even With wrap()

The wrapped client captures: model name, token counts, latency, finish reason.
It does NOT capture: **prompt template structure** — which variables go into which positions.

Without `neatlogs.trace()` + `SystemPromptTemplate`/`UserPromptTemplate`, prompts don't appear in the Neatlogs prompt management dashboard. You cannot version, compare, or A/B test prompts without this.

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
    with neatlogs.trace("summarize_llm", kind="LLM",
                        system_prompt_template=SUMMARIZE_SYS_TPL,
                        user_prompt_template=SUMMARIZE_USER_TPL):
        msgs = SUMMARIZE_SYS_TPL.compile(max_words="200") + SUMMARIZE_USER_TPL.compile(text=text)
        response = await client.chat.completions.create(
            model=settings.model_name,
            messages=msgs,
        )
    return response.choices[0].message.content.strip()
```

## WRONG vs RIGHT

```python
# ❌ WRONG — passing raw strings. Templates won't appear in dashboard.
SYSTEM_PROMPT = "You are a document summarizer."

def summarize(text: str) -> str:
    with neatlogs.trace("summarize_llm", kind="LLM",
                        system_prompt_template=SYSTEM_PROMPT,   # RAW STRING = BROKEN
                        user_prompt_template=f"Summarize: {text}"):  # RAW STRING = BROKEN
        response = client.chat.completions.create(model="gpt-4o", messages=[...])
    return response.choices[0].message.content
```

```python
# ✅ RIGHT — using SystemPromptTemplate/UserPromptTemplate objects
from neatlogs import SystemPromptTemplate, UserPromptTemplate

SUMMARIZE_SYS_TPL = SystemPromptTemplate([
    {"role": "system", "content": "You are a document summarizer."}
])
SUMMARIZE_USER_TPL = UserPromptTemplate([
    {"role": "user", "content": "Summarize: {{text}}"}
])


def summarize(text: str) -> str:
    with neatlogs.trace("summarize_llm", kind="LLM",
                        system_prompt_template=SUMMARIZE_SYS_TPL,
                        user_prompt_template=SUMMARIZE_USER_TPL):
        msgs = SUMMARIZE_SYS_TPL.compile() + SUMMARIZE_USER_TPL.compile(text=text)
        response = client.chat.completions.create(model="gpt-4o", messages=msgs)
    return response.choices[0].message.content
```

## Anthropic — different API shape (system= is a separate param)

Anthropic's `client.messages.create()` does NOT take the system prompt inside `messages`. It takes `system=` (a string) and `messages=` (user/assistant turns only). So define the **system template as a STRING** template — `compile()` then returns a string, perfect for `system=`. The user template stays list-form for `messages=`.

`compile()` returns a **str** when the template was built from a string, and a **list[dict]** when built from a list. Use that:

```python
from neatlogs import SystemPromptTemplate, UserPromptTemplate

# system as a STRING template → compile() returns a str (for system=)
SUMMARIZE_SYS_TPL = SystemPromptTemplate(
    "You are a conversation summarizer. Keep the summary under {{max_words}} words."
)
# user as a list template → compile() returns list[dict] (for messages=)
SUMMARIZE_USER_TPL = UserPromptTemplate([
    {"role": "user", "content": "Summarize:\n\n{{text}}"}
])


@neatlogs.span(kind="CHAIN")
async def summarize(text: str) -> str:
    with neatlogs.trace("summarize_llm", kind="LLM",
                        system_prompt_template=SUMMARIZE_SYS_TPL,
                        user_prompt_template=SUMMARIZE_USER_TPL):
        system_str = SUMMARIZE_SYS_TPL.compile(max_words="200")   # → str
        msgs = SUMMARIZE_USER_TPL.compile(text=text)              # → list[dict]
        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=512,
            system=system_str,     # ← compiled system string actually used
            messages=msgs,         # ← compiled user messages actually used
        )
    return response.content[0].text
```

```python
# ❌ WRONG (Anthropic) — templates declared in trace() but the call uses a separate raw
# string + hand-built dict. The template is decorative and disconnected from the real prompt.
with neatlogs.trace("summarize_llm", kind="LLM",
                    system_prompt_template=SUMMARIZE_SYS_TPL,
                    user_prompt_template=SUMMARIZE_USER_TPL):
    response = await client.messages.create(
        system=SUMMARIZE_SYSTEM_PROMPT,                        # raw string, NOT SUMMARIZE_SYS_TPL.compile()
        messages=[{"role": "user", "content": user_content}],  # hand-built, NOT SUMMARIZE_USER_TPL.compile(...)
    )
```

The same rule holds for every provider: **whatever you declare in `trace()` you must `.compile()` and pass into the actual call.** Match `compile()`'s return type to the slot — str template → `system=`, list template → `messages=`.

## How to Convert Existing Prompts to Templates

| Before | After |
|--------|-------|
| `f"Summarize: {text}"` | `UserPromptTemplate([{"role": "user", "content": "Summarize: {{text}}"}])` |
| `f"You are a {role} assistant"` | `SystemPromptTemplate([{"role": "system", "content": "You are a {{role}} assistant"}])` |
| `"Extract entities from the text."` (static) | `SystemPromptTemplate([{"role": "system", "content": "Extract entities from the text."}])` |
| `SYSTEM_PROMPT` (constant string) | `SystemPromptTemplate([{"role": "system", "content": "...the constant value..."}])` |

Even static prompts get templates — this makes them visible in the dashboard for prompt management.

## CRITICAL: `{{variables}}` are for dynamic data, NOT for whole authored prompts

A `{{variable}}` represents genuinely dynamic data filled in per call — user input, retrieved context, a runtime value. It must NOT stand in for an entire authored prompt. A template whose whole content is one variable (`{{system_prompt}}`) is a useless passthrough: the dashboard shows `{{system_prompt}}` instead of the real wording, so the prompt can't be versioned, diffed, or managed.

### The runtime-dispatch trap

When the code SELECTS a system prompt from a fixed set of constants at runtime, each constant is its OWN template — do NOT collapse them into one `{{system_prompt}}` template.

```python
# Source code:
CODING_PROMPT  = "You are an expert coding assistant..."
WRITING_PROMPT = "You are a skilled writing assistant..."
GENERAL_PROMPT = "You are a helpful general-purpose assistant..."

def get_system_prompt(intent): return {"coding":CODING_PROMPT, ...}.get(intent, GENERAL_PROMPT)
...
system_prompt = get_system_prompt(intent)   # one of 3 authored prompts
```

```python
# ❌ WRONG — whole prompt as a variable. Dashboard shows "{{system_prompt}}", not the wording.
CHAT_SYS_TPL = SystemPromptTemplate([{"role": "system", "content": "{{system_prompt}}"}])
sys = CHAT_SYS_TPL.compile(system_prompt=get_system_prompt(intent))

# ✅ RIGHT — one template per authored prompt; pick by intent. Each is versionable.
CODING_SYS_TPL  = SystemPromptTemplate([{"role": "system", "content": "You are an expert coding assistant..."}])
WRITING_SYS_TPL = SystemPromptTemplate([{"role": "system", "content": "You are a skilled writing assistant..."}])
GENERAL_SYS_TPL = SystemPromptTemplate([{"role": "system", "content": "You are a helpful general-purpose assistant..."}])
_SYS_TPLS = {"coding": CODING_SYS_TPL, "writing": WRITING_SYS_TPL, "general": GENERAL_SYS_TPL}

sys_tpl = _SYS_TPLS.get(intent, GENERAL_SYS_TPL)
with neatlogs.trace("chat", kind="LLM", system_prompt_template=sys_tpl, user_prompt_template=CHAT_USER_TPL):
    msgs = sys_tpl.compile() + CHAT_USER_TPL.compile(message=user_message)
    ...
```

Rule: if you find yourself writing `content: "{{x}}"` where `x` is an entire prompt string (not a snippet of dynamic data), STOP — bake the real prompt text into the template(s) instead. Use real variables only for the parts that genuinely change per call (`{{context}}`, `{{question}}`, `{{user_message}}`).

## Template Rules

- Templates use `{{double_braces}}` for variables
- `.compile(var=value)` renders and returns a `list[dict]` ready for `messages=`
- Combine system + user: `msgs = sys_tpl.compile(...) + user_tpl.compile(...)`
- Define at **module level**, not inside functions
- Import: `from neatlogs import SystemPromptTemplate, UserPromptTemplate`
- Name convention: `UPPERCASE_DESCRIPTIVE_TPL` (e.g., `EXTRACT_SYS_TPL`, `COMBINE_USER_TPL`)

## Multiple LLM Calls in One Function

Wrap each call in its own `trace()` with its own templates:

```python
@neatlogs.span(kind="CHAIN")
async def research(topic):
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

- [ ] Every function with a direct LLM call has `with neatlogs.trace(...)` around the call
- [ ] Every `trace()` has both `system_prompt_template=` and `user_prompt_template=` parameters
- [ ] **The templates are `.compile()`d and the compiled output is what's passed to the actual call** (`messages=msgs` for OpenAI; `system=`+`messages=` for Anthropic). A template declared in trace() but not used in the call is BROKEN.
- [ ] Templates use `SystemPromptTemplate(...)` / `UserPromptTemplate(...)` objects, NOT raw strings
- [ ] Templates are defined at module level with `UPPERCASE_TPL` naming
- [ ] Template variables use `{{double_braces}}` and are bound via `.compile(var=value)`
- [ ] `from neatlogs import SystemPromptTemplate, UserPromptTemplate` is in each file that uses them
