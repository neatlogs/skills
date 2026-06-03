# Step 4: Create + Attach the Callback Handler

## Action

1. Create ONE handler: `handler = neatlogs.langchain_handler()`. Make it reachable wherever models are invoked (module-level constant, or pass it in).
2. Pass it via `config={"callbacks": [handler]}` on the model/chain calls you want traced.

```python
import neatlogs
from langchain_openai import ChatOpenAI

handler = neatlogs.langchain_handler()

model = ChatOpenAI(model="gpt-4o")
result = model.invoke("Hello", config={"callbacks": [handler]})
```

## LangChain (chains / LCEL)

Attach on the outer `.invoke()` / `.ainvoke()` / `.stream()` of the chain you run:

```python
chain = prompt | model | parser
result = chain.invoke({"question": q}, config={"callbacks": [handler]})
```

## LangGraph — attach at the MODEL level inside nodes, NOT graph.invoke()

This is the important rule. Attach the handler to the **model call inside each node**. Do NOT attach it to `graph.invoke()` / `graph.ainvoke()` — that duplicates events and produces noisy chain spans.

```python
handler = neatlogs.langchain_handler()

def analyst_node(state):
    # ✅ model level
    response = llm.invoke(state["messages"], config={"callbacks": [handler]})
    return {"messages": [response]}

# ❌ DO NOT do this — graph-level attach duplicates spans
# graph.invoke(state, config={"callbacks": [handler]})
```

If a node binds tools (`llm_with_tools = llm.bind_tools(...)`), attach on that call the same way: `llm_with_tools.invoke(msgs, config={"callbacks": [handler]})`.

## Handler reuse

One handler instance is fine for the whole app — reuse it across nodes/calls. Creating a fresh handler per call also works but is unnecessary.

## WRONG vs RIGHT

```python
# ❌ WRONG — model invoked with no callbacks. Nothing traced.
response = llm.invoke(messages)

# ❌ WRONG — LangGraph handler attached at graph level. Duplicate / noisy spans.
graph.invoke(state, config={"callbacks": [handler]})

# ✅ RIGHT — handler attached at the model call inside the node.
response = llm.invoke(messages, config={"callbacks": [handler]})
```

## Verify BEFORE moving to step 5

1. Exactly one `neatlogs.langchain_handler()` is created and reused.
2. Every model/chain call you want traced has `config={"callbacks": [handler]}`.
3. LangGraph: the handler is attached at the model level inside nodes, NOT on `graph.invoke()`.
4. `import neatlogs` is present in the file that creates the handler.
