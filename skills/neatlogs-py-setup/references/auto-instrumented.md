# Auto-Captured — What NOT to Decorate

Once you've wrapped the client/agent (`neatlogs.wrap`), attached the LangChain handler, or registered the OpenAI Agents processor, the calls below are captured automatically. Do NOT add `@span` to functions that ONLY wrap these calls.

## `neatlogs.wrap(OpenAI())` covers:
- `client.chat.completions.create()` → LLM span
- `client.embeddings.create()` → EMBEDDING span
- `client.responses.create()` → LLM span
- All streaming variants

## `neatlogs.wrap(Anthropic())` covers:
- `client.messages.create()` → LLM span
- `client.messages.stream()` → LLM span
- Streaming with TTFT metrics

## `neatlogs.wrap(genai.Client())` (Google GenAI) covers:
- `client.models.generate_content()` → LLM span
- `client.models.generate_content_stream()` → LLM span

## `neatlogs.langchain_handler()` (attached via `config={"callbacks": [handler]}`) covers:
- `chain.invoke()` / `chain.ainvoke()` → CHAIN span
- LLM calls within chains (ChatOpenAI, ChatAnthropic) → LLM span
- retriever calls → RETRIEVER span
- **ALL `@tool`-decorated functions** (via ToolNode) → TOOL span
- LangGraph node executions → spans

### LangChain: what this means for you
- Do NOT add `@neatlogs.span()` to any function with `@tool` from `langchain_core.tools`
- Do NOT add `@neatlogs.span()` to graph node functions (planner_node, analyst_node)
- DO still add `with neatlogs.trace("<name>", kind="LLM")` + prompt templates inside nodes (for prompt management) — `name` is the required first positional arg
- DO add `@neatlogs.span(kind="WORKFLOW")` on the top-level user-facing function that calls `graph.invoke()`
- Attach the handler at the MODEL level inside nodes, NOT on `graph.invoke()` (avoids duplicates)

## `neatlogs.wrap(crew)` (CrewAI) covers:
- `crew.kickoff()` → WORKFLOW span
- Agent task execution → AGENT span
- `BaseTool.run` (tool calls) → TOOL span
- `LLM.call` (the model request) → LLM span — no provider instrumentor needed

## `neatlogs.openai_agents_processor()` (registered via `add_trace_processor`) covers:
- `Runner.run()` and each Agent turn → AGENT span
- `@function_tool` functions → TOOL span
- Handoffs → AGENT span
- Guardrails → GUARDRAIL span
- LLM calls → LLM span

## `neatlogs.wrap(agent)` (Pydantic AI) covers:
- `agent.run()` / `run_sync()` / `run_stream()` → AGENT span
- Tool calls → TOOL span
- Model requests → LLM span

## `neatlogs.wrap(module)` (DSPy) covers:
- Module `__call__` (Predict / ChainOfThought / ReAct / custom) → CHAIN span
- `dspy.LM.__call__` → LLM span

## `neatlogs.wrap(agent)` (Agno) covers:
- `run` / `arun` (incl. streaming) → AGENT / TEAM / WORKFLOW span
- Model invocation → LLM span
- Tool calls → TOOL span

## `neatlogs.wrap(runner)` (Google ADK) covers:
- `runner.run()` / `run_async()` → WORKFLOW span (with token usage + tool-call metadata)

## Strands (native OTel, captured by `init()` alone)
- `invoke_agent` → AGENT span
- model call → LLM span
- `execute_tool` → TOOL span

## `instrumentations=[...]` (fallback providers `wrap()` doesn't cover)
- `"bedrock"` → `client.converse()` / `client.invoke_model()` → LLM span
- `"groq"` / `"cohere"` / `"mistralai"` / `"together"` / `"litellm"` → provider LLM calls → LLM span
- Embeddings: `"openai"` / `"cohere"` provider classes → EMBEDDING span (when the project embeds through them)

## Rule of Thumb

If function ONLY does: `return client.chat.completions.create(...)` → skip `@span`.
If function does: build context + call LLM + parse result → decorate as CHAIN.
If function has `@tool` / `@function_tool` from a framework → NEVER add `@span` (creates duplicates).

The dividing line is **meaningful work around the call**, not the presence of the call itself.

## What IS still needed on auto-captured calls

Even when a call is auto-captured, you should STILL wrap it with:
```python
with neatlogs.trace("name", kind="LLM",
                    system_prompt_template=SYS_TPL,
                    user_prompt_template=USER_TPL):
```

This captures the **prompt template structure** for the prompt management dashboard. The wrapper/handler/processor captures metadata (model, tokens, latency) but NOT template variables.
