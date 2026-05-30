# Auto-Instrumented — What NOT to Decorate

When these libraries are in `instrumentations=[]`, their calls are automatically traced. Do NOT add `@span` to functions that ONLY wrap these calls.

## "openai" covers:
- `client.chat.completions.create()` → LLM span
- `client.embeddings.create()` → EMBEDDING span
- `client.responses.create()` → LLM span
- All streaming variants

## "anthropic" covers:
- `client.messages.create()` → LLM span
- `client.messages.stream()` → LLM span
- Streaming with TTFT metrics

## "google_genai" covers:
- `client.models.generate_content()` → LLM span
- `client.models.generate_content_stream()` → LLM span

## "langchain" covers:
- `chain.invoke()` / `chain.ainvoke()` → CHAIN span
- LLM calls within chains (ChatOpenAI, ChatAnthropic) → LLM span
- `retriever.get_relevant_documents()` → RETRIEVER span
- **ALL `@tool`-decorated functions** → TOOL span
- **All LangGraph node executions** → spans
- **ToolNode tool dispatch** → TOOL span

### LangChain: what this means for you
- Do NOT add `@neatlogs.span()` to any function with `@tool` from `langchain_core.tools`
- Do NOT add `@neatlogs.span()` to graph node functions (planner_node, analyst_node)
- DO still add `with neatlogs.trace(kind="LLM")` + prompt templates inside nodes (for prompt management)
- DO add `@neatlogs.span(kind="WORKFLOW")` on the top-level user-facing function that calls `graph.invoke()`

## "crewai" covers:
- `crew.kickoff()` → WORKFLOW span
- Agent task execution → AGENT span
- `@tool`-decorated functions → TOOL span
- LLM calls (via litellm) → LLM span

## "llamaindex" covers:
- Query engine queries → CHAIN span
- LLM calls → LLM span
- Retriever calls → RETRIEVER span
- Tool classes → TOOL span

## "openai_agents" covers:
- Agent.run() → AGENT span
- Tool calls → TOOL span
- LLM calls → LLM span

## "pydantic_ai" covers:
- Agent.run() → AGENT span
- Tool calls → TOOL span
- LLM calls → LLM span

## "bedrock" covers:
- `client.converse()` / `client.invoke_model()` → LLM span

## "chromadb" / "pinecone" / "qdrant" covers:
- `collection.query()` → RETRIEVER span
- `collection.add()` → span
- Embedding operations within vector stores

## Rule of Thumb

If function ONLY does: `return client.chat.completions.create(...)` → skip `@span`.
If function does: build context + call LLM + parse result → decorate as CHAIN.
If function has `@tool` from a framework → NEVER add `@span` (creates duplicates).

The dividing line is **meaningful work around the call**, not the presence of the call itself.

## What IS still needed on auto-instrumented calls

Even when a call is auto-instrumented, you should STILL wrap it with:
```python
with neatlogs.trace("name", kind="LLM",
                    system_prompt_template=SYS_TPL,
                    user_prompt_template=USER_TPL):
```

This captures the **prompt template structure** for the prompt management dashboard. Auto-instrumentation captures metadata (model, tokens, latency) but NOT template variables.
