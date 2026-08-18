# Step 4: Attach the Handler; Add a WORKFLOW Only for App Orchestration

The handler owns chains, graph nodes, tools, retrievers, and LLM calls and self-roots a parentless supported run. Always pass `{ callbacks: [handler] }` at the correct invocation boundary. Wrap the user-facing entry with `span({ kind:'WORKFLOW' }, fn)` only when that function owns meaningful pre/post work or coordinates multiple runs; do not add it around a single pass-through call just to make a trace render.

```typescript
import { span, langchainHandler } from "neatlogs";

const handler = langchainHandler();

const runAgent = span({ kind: "WORKFLOW", name: "run_agent" }, async (query: string) => {
  validateQuery(query); // real app-owned pre-processing
  const response = await llm.invoke(query, { callbacks: [handler] });
  const answer = normalizeAnswer(response.content); // real app-owned post-processing
  await saveAuditRecord({ query, answer });
  return answer;
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

// App-owned entry point with real surrounding orchestration — optional WORKFLOW;
// the handler still goes on the graph invocation:
const run = span({ kind: "WORKFLOW", name: "run_graph" }, async (input) => {
  validateInput(input);
  const result = await compiledGraph.invoke(input, { callbacks: [handler] });
  await saveRunResult(result);
  return result;
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
- [ ] At most one app-owned `span({ kind:"WORKFLOW" }, ...)` on a real user-facing orchestrator; zero is correct for a single supported invocation.
- [ ] Plain LangChain: `{ callbacks: [handler] }` on each model/chain invocation.
- [ ] LangGraph: `{ callbacks: [handler] }` on the graph invocation (`app.invoke(...)`), NOT on per-node `llm.invoke()`.
- [ ] No chain/node/tool/`llm.invoke()` wrapped in `span()`/`trace()`.
