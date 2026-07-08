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

## LangGraph — attach at the GRAPH invocation, NOT the per-node model call

This is the important rule, and it is the OPPOSITE of plain LangChain. Attach the handler on the **graph invocation** (`app.invoke()` / `app.ainvoke()` / `app.stream()` / `app.astream()`). Do NOT attach it on a per-node `llm.invoke()`.

Why: LangGraph fires the per-node `on_chain_start` only on the **graph-level callback manager**. A handler passed to a single node's model call never sees the node boundaries — so you get no node spans, and the LLM span orphans to the workflow root (flat, no node hierarchy). Attach once at the graph invocation and each node gets its own span with its LLM nested under it.

```python
handler = neatlogs.langchain_handler()

def analyst_node(state):
    # nodes invoke the model normally — NO per-node handler
    response = llm.invoke(state["messages"])
    return {"messages": [response]}

# ✅ graph level — nodes + nested LLM/tool spans all appear
app.invoke(state, config={"callbacks": [handler]})

# ❌ DO NOT do this — per-node attach yields no node spans; the LLM orphans to the root
# llm.invoke(state["messages"], config={"callbacks": [handler]})
```

Tool-bound LLMs inside a node (`llm_with_tools = llm.bind_tools(...)`) also need no per-node handler — the graph-invocation handler covers them.

## Handler reuse

One handler instance is fine for the whole app — reuse it across nodes/calls. Creating a fresh handler per call also works but is unnecessary.

## WRONG vs RIGHT

```python
# Plain LangChain (LCEL chain / bare model call):
# ❌ WRONG — model invoked with no callbacks. Nothing traced.
response = llm.invoke(messages)
# ✅ RIGHT — attach on the model / chain call.
response = llm.invoke(messages, config={"callbacks": [handler]})

# LangGraph:
# ❌ WRONG — per-node attach. No node spans; the LLM orphans to the root.
response = llm.invoke(state["messages"], config={"callbacks": [handler]})
# ✅ RIGHT — attach at the graph invocation. Nodes + nested LLMs all get spans.
app.invoke(state, config={"callbacks": [handler]})
```

## Verify BEFORE moving to step 5

1. Exactly one `neatlogs.langchain_handler()` is created and reused.
2. Plain LangChain: every model/chain call you want traced has `config={"callbacks": [handler]}`.
3. LangGraph: the handler is attached at the graph invocation (`app.invoke(..., config={"callbacks": [handler]})`), NOT on the per-node `llm.invoke()`.
4. `import neatlogs` is present in the file that creates the handler.
