# Step 6: Keep LangChain LLM Calls Handler-Owned

The LangChain callback handler emits the canonical CHAIN/node, LLM, TOOL, and RETRIEVER spans. Once the handler is attached at the correct invocation boundary, leave model and node code unchanged.

```python
handler = neatlogs.langchain_handler()
result = model.invoke(messages, config={"callbacks": [handler]})

# Async plain LangChain is also handler-owned.
result = await model.ainvoke(messages, config={"callbacks": [handler]})
async for chunk in model.astream(messages, config={"callbacks": [handler]}):
    consume(chunk)
```

For LangGraph, attach the handler once at `app.invoke`/`ainvoke`/`stream`/`astream`; do not attach it per node and do not add manual instrumentation inside nodes. In an `async def` node, use `await llm.ainvoke(...)`. Consume `app.astream(...)` with `async for` rather than awaiting the iterator. The Python handler subclasses LangChain's async callback handler and supports async invocations; it is not a sync-only handler.

Never wrap `llm.invoke()`/`ainvoke()`/`stream()`/`astream()` in `neatlogs.trace(kind="LLM")` or an LLM decorator. Never rewrite the user's LangChain messages solely for instrumentation. The handler captures the actual messages sent to the model.

A manual LLM span is valid only for an unsupported/raw model call outside LangChain that no wrapper, handler, hook, processor, or instrumentor captures.

## Verification checklist

- [ ] The handler is attached once at the correct plain-LangChain or LangGraph invocation boundary.
- [ ] No graph node, chain, model call, tool, or retriever has an extra Neatlogs decorator/trace.
- [ ] No separate provider instrumentor captures the same LangChain model call.
- [ ] A runtime trace contains one nested LLM span per real model call and preserves node hierarchy.
