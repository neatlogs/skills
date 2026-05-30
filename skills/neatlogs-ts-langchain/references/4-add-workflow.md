# Step 4: Add the WORKFLOW Span (and ONLY that)

The langchain instrumentor auto-traces chains, graph nodes, tools, retrievers, and LLM calls. The one thing it can't do is create the trace root. Wrap the user-facing entry — the function that runs the chain/graph/agent — with `span({ kind:'WORKFLOW' }, fn)`.

```typescript
import { span } from "neatlogs";

const runAgent = span({ kind: "WORKFLOW", name: "run_agent" }, async (query: string) => {
  const response = await llm.invoke(query);   // auto-traced as LLM
  return response.content;
});

await runAgent("Explain black holes");
```

For LangGraph, wrap the function that calls `graph.invoke()` / `.stream()`:

```typescript
const run = span({ kind: "WORKFLOW", name: "run_graph" }, async (input) => {
  return await compiledGraph.invoke(input);
});
```

## Do NOT wrap anything else

```typescript
// ❌ WRONG — wrapping a chain / node / tool / llm.invoke. Auto-traced → duplicates.
const node = span({ kind: "CHAIN" }, async (state) => llm.invoke(state.messages));   // REMOVE

// ✅ RIGHT — define nodes/chains/tools normally; only the outer entry gets WORKFLOW.
const node = async (state) => ({ messages: [await llm.invoke(state.messages)] });
```

- Graph nodes, chains, LangChain tools, retrievers, `llm.invoke()` → all auto-traced. Leave them alone.
- The ONLY `span()` you add is `kind:"WORKFLOW"` on the entry that runs the chain/graph/agent.

## Verify
- [ ] Exactly one `span({ kind:"WORKFLOW" }, ...)` on the chain/graph/agent entry.
- [ ] No chain/node/tool/`llm.invoke()` wrapped in `span()`/`trace()`.
