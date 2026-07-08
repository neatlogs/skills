# Step 4: Add the WORKFLOW Span + Attach the Handler

The handler traces chains, graph nodes, tools, retrievers, and LLM calls — but it doesn't create the trace root. Wrap the user-facing entry with `span({ kind:'WORKFLOW' }, fn)` and pass `{ callbacks: [handler] }` on LLM/chain invocations inside.

```typescript
import { span, langchainHandler } from "neatlogs";

const handler = langchainHandler();

const runAgent = span({ kind: "WORKFLOW", name: "run_agent" }, async (query: string) => {
  const response = await llm.invoke(query, { callbacks: [handler] });
  return response.content;
});

await runAgent("Explain black holes");
```

For LangGraph, wrap the function that calls `app.invoke()`, and attach the handler on the **graph invocation** — NOT on the per-node `llm.invoke()`. LangGraph fires the per-node `on_chain_start` only on the graph-level callback manager, so a per-node handler never sees the node boundaries (no node spans; the LLM orphans to the root). Nodes invoke the model with no handler:

```typescript
// Inside your node — no per-node handler:
async function researchNode(state) {
  const res = await llm.invoke(state.messages);
  return { messages: [res] };
}

// Entry point — WORKFLOW span AND the handler go here:
const run = span({ kind: "WORKFLOW", name: "run_graph" }, async (input) => {
  return await compiledGraph.invoke(input, { callbacks: [handler] });
});
```

## Do NOT wrap anything else

```typescript
// ❌ WRONG — wrapping a node / llm.invoke with span(). The handler already traces it.
const node = span({ kind: "CHAIN" }, async (state) => llm.invoke(state.messages));

// ✅ RIGHT — define nodes normally; the handler goes on the graph invocation, only the outer entry gets WORKFLOW.
const node = async (state) => ({ messages: [await llm.invoke(state.messages)] });
```

## Verify
- [ ] Exactly one `span({ kind:"WORKFLOW" }, ...)` on the chain/graph/agent entry.
- [ ] Plain LangChain: `{ callbacks: [handler] }` on each model/chain invocation.
- [ ] LangGraph: `{ callbacks: [handler] }` on the graph invocation (`app.invoke(...)`), NOT on per-node `llm.invoke()`.
- [ ] No chain/node/tool/`llm.invoke()` wrapped in `span()`/`trace()`.
