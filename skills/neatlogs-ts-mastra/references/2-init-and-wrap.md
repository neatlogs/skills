# Step 2: init() + wrapMastra

Two pieces: `init()` first (registers the tracer provider), then `wrapMastra()` each Mastra entity and use the wrapped reference.

```typescript
import "dotenv/config";
import { init, flush, shutdown } from "neatlogs";
import { wrapMastra } from "neatlogs/mastra";

await init({
  apiKey: process.env.NEATLOGS_API_KEY ?? "",
  workflowName: "my-mastra-app",
  // instrumentations is OPTIONAL for a pure-Mastra app — wrapMastra captures
  // everything on its own. Only add a provider here if you ALSO call a provider
  // SDK directly outside Mastra. (See "Works with any provider" below.)
});

// Dynamic imports AFTER init so modules are patched at load time.
const { projectManagerAgent } = await import("./agents/index.js");
const { sprintPlanningWorkflow } = await import("./workflows/index.js");

// Wrap each entity. wrapMastra patches in place AND returns it — use the result.
const agent = wrapMastra(projectManagerAgent);
const workflow = wrapMastra(sprintPlanningWorkflow);

// Use the wrapped references exactly like the originals.
const res = await agent.generate("Plan the next sprint.");
console.log(res.text);
```

## What gets captured

A single `agent.generate()` produces a nested tree:

```
AGENT  mastra.agent.<name>
 ├─ LLM   mastra.llm.<model>.doGenerate   (one per model step)
 └─ TOOL  mastra.tool.<tool-id>           (one per tool call)
```

- **AGENT** — input, output, model, system prompt.
- **LLM** — model, provider, token counts (prompt/completion/total), stop reason, invocation parameters (temperature/max_tokens/top_p/…), advertised tools, and tool_calls.
- **TOOL** — tool name, description, input args, output.
- **Streaming** — `agent.stream()` works too: the AGENT span stays open until the stream drains, and the model's `doStream` call nests as an LLM child.

## Other entities

```typescript
const { InMemoryVector } = await import("./vector/index.js");
const { rerank } = await import("@mastra/rag");
import { wrapMastra, wrapMastraRerank } from "neatlogs/mastra";

const vector = wrapMastra(new InMemoryVector());   // query → RETRIEVER, upsert → VECTOR_STORE
const memory = wrapMastra(myMemory);               // recall/saveMessages → CHAIN

// rerank is a standalone function, not an entity — wrap it explicitly:
const tracedRerank = wrapMastraRerank(rerank);     // → RERANKER span
const ranked = await tracedRerank(results, query, model, { topK: 5 });
```

## Wrapping the root Mastra instance

If the app uses a root `Mastra`, wrap it once — the returned proxy auto-wraps every agent/workflow it hands out:

```typescript
const { Mastra } = await import("@mastra/core");
const mastra = wrapMastra(new Mastra({ agents: { projectManagerAgent }, workflows: { sprintPlanningWorkflow } }));
const agent = mastra.getAgent("projectManagerAgent"); // already traced
```

## Works with any provider (openai / anthropic / google / bedrock)

`wrapMastra` is provider-agnostic. It hooks the agent's resolved model at the Mastra router level (`doGenerate`/`doStream` on the AI SDK V2 interface), which is identical across providers — so the LLM span (model name, prompt/completion tokens, stop reason, output, tool_calls) is captured the same way regardless of which model the agent uses.

**You do NOT wrap the provider separately.** A Mastra agent routes its provider call through the model router, not the bare provider SDK, so `wrapMastra(agent)` is the sole capture point — there is no `wrapOpenAI`/`wrapAnthropic` step, and naming the provider in `instrumentations` does NOT produce duplicate LLM spans. (The provider entry only matters if the same app ALSO calls a provider SDK directly, outside Mastra.)

Each provider just needs its API key in `.env` and the matching Mastra model string — no `instrumentations` entry and no provider wrapper required:

| Mastra model string | API key env var | `instrumentations` entry |
|---------------------|-----------------|--------------------------|
| `openai/gpt-4o-mini` | `OPENAI_API_KEY` | not needed (optional `"openai"`) |
| `anthropic/claude-haiku-4-5` | `ANTHROPIC_API_KEY` | not needed (optional `"anthropic"`) |
| `google/gemini-2.5-flash` | `GOOGLE_GENERATIVE_AI_API_KEY` (and/or `GOOGLE_API_KEY`) | not needed (optional `"google_genai"`) |
| `bedrock/...` | AWS credentials | not needed (optional `"bedrock"`) |

```typescript
// Anthropic — no instrumentations needed
await init({ apiKey: process.env.NEATLOGS_API_KEY, workflowName: "my-app" });
const agent = wrapMastra(new Agent({ id: "pm", name: "PM", instructions: "...", model: "anthropic/claude-haiku-4-5" }));

// Google — no instrumentations needed
await init({ apiKey: process.env.NEATLOGS_API_KEY, workflowName: "my-app" });
const agent = wrapMastra(new Agent({ id: "pm", name: "PM", instructions: "...", model: "google/gemini-2.5-flash" }));
```

The `instrumentations` entry is only for provider SDKs called DIRECTLY outside Mastra. If the app does that for several providers, list them all, e.g. `instrumentations: ["openai", "anthropic"]`.

## Tool signature (Mastra 1.x)

Tools MUST use the 1.x `execute` signature — input fields on the FIRST argument:

```typescript
// ✅ Mastra 1.x
createTool({ id: "search", inputSchema, execute: async (input) => ({ hits: search(input.query) }) });

// ❌ Pre-1.0 — `input` is undefined on @mastra/core >= 1.0, throws at runtime
createTool({ id: "search", execute: async ({ context }) => ({ hits: search(context.query) }) });
```

## Verify
1. `await init(...)` runs before the dynamic `import()` of `@mastra/core`.
2. Each provider used by an agent has its API key in `.env` (no `instrumentations` entry required for Mastra-routed calls).
3. Every entity you care about is passed through `wrapMastra()` and the RETURNED reference is the one called.
4. Tools use the 1.x `(inputData)` execute signature.
