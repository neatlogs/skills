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

For LangGraph, wrap the function that calls `graph.invoke()`, but attach the handler on the **model call inside each node** — NOT on graph.invoke():

```typescript
// Inside your node:
async function researchNode(state) {
  const res = await llm.invoke(state.messages, { callbacks: [handler] });
  return { messages: [res] };
}

// Entry point — only this gets WORKFLOW:
const run = span({ kind: "WORKFLOW", name: "run_graph" }, async (input) => {
  return await compiledGraph.invoke(input);
});
```

## Do NOT wrap anything else

```typescript
// ❌ WRONG — wrapping a node / llm.invoke with span(). The handler already traces it.
const node = span({ kind: "CHAIN" }, async (state) => llm.invoke(state.messages));

// ✅ RIGHT — define nodes normally; only the outer entry gets WORKFLOW.
const node = async (state) => ({ messages: [await llm.invoke(state.messages, { callbacks: [handler] })] });
```

## Verify
- [ ] Exactly one `span({ kind:"WORKFLOW" }, ...)` on the chain/graph/agent entry.
- [ ] `{ callbacks: [handler] }` on model/chain invocations inside nodes.
- [ ] No chain/node/tool/`llm.invoke()` wrapped in `span()`/`trace()`.
