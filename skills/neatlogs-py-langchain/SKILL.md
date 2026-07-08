---
name: neatlogs-py-langchain
description: Use when adding neatlogs observability to a Python project that uses LangChain or LangGraph (imports `langchain*` / `langgraph`, builds chains, runnables, or a graph).
compatibility: Neatlogs Wizard Agent
metadata:
  author: neatlogs
  version: "3.0"
  language: python
  framework: langchain
---

# Neatlogs Python Setup — LangChain / LangGraph

This project uses LangChain or LangGraph. Neatlogs offers **two ways** to instrument it:

1. **`neatlogs.langchain_handler()`** — a LangChain callback handler you attach per call via `config={"callbacks": [handler]}`. This is the **recommended, first-class** path (LangChain's own callback system; explicit control over exactly which calls are traced). This skill uses it throughout.
2. **`instrumentations=["langchain"]`** on `init()` — zero-touch auto-instrumentation (OpenInference) that traces LangChain/LangGraph globally without editing call sites. Use this when you can't (or don't want to) thread a handler through your code.

Pick ONE — don't combine them (that double-traces). The rest of this skill shows the handler approach.

## Core mechanism — `neatlogs.langchain_handler()`

Create ONE handler and pass it via `config={"callbacks": [handler]}` on the calls you want traced. The handler emits the span tree from LangChain's callback events:

```
CHAIN  chain / graph execution
  ↳ LLM        chat-model / llm call
  ↳ TOOL       @tool invocation (via ToolNode)
  ↳ RETRIEVER  retriever call
```

```python
import neatlogs
from langchain_openai import ChatOpenAI

handler = neatlogs.langchain_handler()
model = ChatOpenAI(model="gpt-4o")
result = model.invoke("Hello", config={"callbacks": [handler]})
```

### LangGraph: attach at the GRAPH invocation — NOT the per-node model call

For LangGraph, attach the handler at the **graph invocation** (`app.invoke(...)` / `ainvoke` / `stream` / `astream`), not on the per-node `llm.invoke()`. LangGraph fires the per-node `on_chain_start` only on the **graph-level callback manager**, so a handler passed to a single node's model call never sees the node boundaries — you get no node spans and the LLM span orphans to the workflow root (flat, no node hierarchy). Attach once at the graph invocation and each node gets its own span with the LLM nested under it (a manual `neatlogs.trace()` / `@span` inside a node nests under the node too).

```python
def analyst_node(state):
    response = llm.invoke(messages)                                    # no per-node handler
    return {"messages": [response]}

# ✅ attach at the graph invocation — nodes + nested LLMs all get spans
app.invoke(state, config={"callbacks": [handler]})                     # graph level ✅
# NOT: llm.invoke(messages, config={"callbacks": [handler]})           # per-node ❌ (no node spans, LLM orphans)
```

(Plain LangChain — LCEL chains / bare `model.invoke()` — is the opposite: attach per model/chain call as in the example above. The graph-level rule is LangGraph-specific.)

### Deep Agents (`deepagents`) — prebuilt harness, attach on the top-level invoke

Deep Agents (`from deepagents import create_deep_agent`) is a LangGraph harness — you do NOT write the nodes, so there's no per-node model call to attach to. Pass the handler on the agent's top-level `invoke` / `ainvoke` / `stream`:

```python
handler = neatlogs.langchain_handler()
agent = create_deep_agent(model="openai:gpt-4o-mini", tools=[...], system_prompt="...")
result = agent.invoke(
    {"messages": [{"role": "user", "content": "..."}]},
    config={"callbacks": [handler]},
)
```

For hand-written LangGraph (your own nodes) as well as prebuilt harnesses (Deep Agents), the top-level / graph invocation is the attach point — use it. (Consistent with the graph-level rule above.)

Combine with `@neatlogs.span` / `neatlogs.trace` / `neatlogs.log` for your own orchestration; the handler's spans nest under your manual spans.

## What the handler captures (DO NOT manually decorate)

- Chat-model / LLM calls → LLM span (model, tokens, latency)
- `@tool` invocations via ToolNode → TOOL span
- Retriever calls → RETRIEVER span
- Chain / node execution → CHAIN span

## Steps

1. **Install SDK** → `references/1-install-sdk.md`
2. **Add init()** → `references/2-add-init.md`
3. **Set environment variables** → `references/3-set-env.md`
4. **Create + attach the callback handler** → `references/4-attach-handler.md`
5. **Add a WORKFLOW span on your entry point** → `references/5-add-workflow.md`
6. **Attach trace() + prompt templates around LLM calls** → `references/6-wrap-llm-calls.md`
7. **Verify tool functions are untouched** → `references/7-verify-tools.md`
7.5. **Embeddings: decorate ONLY custom ones** → `references/7.5-embeddings.md`
8. **Add flush/shutdown** → `references/8-flush-shutdown.md`

## Rules (apply to ALL steps)

- `neatlogs.init()` MUST execute BEFORE any LangChain library imports.
- If `load_dotenv()` exists, it MUST run BEFORE `neatlogs.init()`.
- This skill uses the **callback handler**; if you go that route, do NOT ALSO pass `instrumentations=["langchain"]` to `init()` — running both double-traces. (`instrumentations=["langchain"]` is a valid standalone alternative — see the intro — just don't combine the two. Provider instrumentors for embeddings are a separate concern — see step 7.5.)
- Create ONE `neatlogs.langchain_handler()` and pass it via `config={"callbacks": [handler]}`. For plain LangChain (LCEL chains / bare model calls) attach per model/chain call. For LangGraph attach at the graph invocation (`app.invoke(..., config={"callbacks": [handler]})`), NOT the per-node `llm.invoke()`.
- Never hardcode API keys in source. Use `os.getenv()`.
- Add imports ONLY for what a file actually uses:
  - File calls `neatlogs.langchain_handler(...)` / `neatlogs.span(...)` / `neatlogs.trace(...)` → add `import neatlogs`.
  - File only defines `SystemPromptTemplate`/`UserPromptTemplate` objects → add ONLY `from neatlogs import SystemPromptTemplate, UserPromptTemplate`. Do NOT add a bare `import neatlogs`.
- When present, `import neatlogs` goes at module top level, never inside functions.
- `@neatlogs.span()` goes BELOW framework decorators, closest to `def`.
- Minimal edits only. Add the handler + decorators + imports. Do not reformat or refactor.
- NEVER add `@neatlogs.span()` to `@tool` functions or LangGraph node functions.
- The ONLY `@span(kind="WORKFLOW")` you add is on the user-facing entry point. `@span(kind="EMBEDDING")` is added ONLY for custom embedders (step 7.5).

## Reference

- Span kinds → `references/span-kinds.md`
- Sessions & end-users (per-turn `identify()` for customer analytics) → `references/sessions-and-end-users.md`
