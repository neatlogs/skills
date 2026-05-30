# Step 4: Verify — wrap every entity, use the wrapped reference, don't double-wrap

## 1. Every entity you want traced is passed through `wrapMastra()`

Grep for `new Agent(`, `createWorkflow(`, `new Mastra(`, vector-store and memory construction. Each entity that should appear in traces must be wrapped:

```typescript
const agent = wrapMastra(projectManagerAgent);
const workflow = wrapMastra(sprintPlanningWorkflow);
const vector = wrapMastra(new InMemoryVector());
const memory = wrapMastra(myMemory);
```

Or wrap the root `Mastra` once to cover all agents/workflows it exposes:

```typescript
const mastra = wrapMastra(new Mastra({ agents, workflows }));
```

## 2. The CALLED reference is the wrapped one

`wrapMastra` patches in place AND returns the entity, so either works — but make sure the code path that actually runs uses a wrapped entity, not a separate unwrapped import.

```typescript
// ✅ RIGHT
const agent = wrapMastra(projectManagerAgent);
await agent.generate("...");

// ❌ WRONG — wrapped a copy but called the raw export elsewhere
wrapMastra(projectManagerAgent);
import { projectManagerAgent } from "./agents"; // calling this unwrapped path = no spans
```

## 3. Don't double-wrap

- Do NOT also put `span()`/`trace()` around a wrapped Mastra call — `wrapMastra` already opens the parent span. (A `span()` WORKFLOW grouping multiple separate calls is fine; never wrap a single already-wrapped call.)
- `wrapMastra` is idempotent — calling it twice on the same entity is a no-op, not a double-trace.

## 4. Tools use the Mastra 1.x signature

```typescript
// ✅ 1.x — input fields on the first arg
createTool({ id: "search", inputSchema, execute: async (input) => run(input.query) });
// ❌ pre-1.0 — throws "Cannot read properties of undefined" on @mastra/core >= 1.0
createTool({ id: "search", execute: async ({ context }) => run(context.query) });
```

## 5. rerank uses `wrapMastraRerank`

`rerank()` is a standalone function, not an entity, so `wrapMastra` won't catch it. Wrap it explicitly: `const tracedRerank = wrapMastraRerank(rerank)`.

## Expected span tree (single agent run)

```
AGENT  mastra.agent.<name>
 ├─ LLM   mastra.llm.<model>.doGenerate   (per model step)
 └─ TOOL  mastra.tool.<id>                (per tool call)
```

## Verification
- [ ] Each traced entity is passed through `wrapMastra()` and the wrapped reference is the one called.
- [ ] No `span()`/`trace()` wraps a single already-wrapped Mastra call.
- [ ] Tools use the 1.x `(inputData)` execute signature.
- [ ] `rerank` (if used) goes through `wrapMastraRerank`.
