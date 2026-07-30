# Step 2: init() + piAgentHooks

## Contents

- [Setup](#step-2-init--piagenthooks)
- [Captured spans](#what-gets-captured)
- [AgentHarness](#agentharness)
- [Idempotency and multiple agents](#wrapping-is-idempotent)
- [Custom parent spans](#nesting-under-your-own-span)
- [Providers](#works-with-any-provider)
- [Verification](#verify)

Two pieces: `init()` first (registers the tracer provider), then `piAgentHooks()` each `Agent` and use the wrapped reference.

```typescript
import "dotenv/config";
import { init, flush, shutdown } from "neatlogs";
import { piAgentHooks } from "neatlogs/pi-agent";
// Plain static imports are fine — piAgentHooks subscribes to the INSTANCE you
// pass, not the module, so there is no import-order rule.
import { Agent } from "@earendil-works/pi-agent-core";
import { Type, createModels } from "@earendil-works/pi-ai";
import { openaiProvider } from "@earendil-works/pi-ai/providers/openai";

await init({
  apiKey: process.env.NEATLOGS_API_KEY ?? "",
  workflowName: "my-pi-app",
  // NO instrumentations key — piAgentHooks captures everything on its own.
});

const models = createModels();
models.setProvider(openaiProvider());
const model = models.getModel("openai", "gpt-4o-mini");
if (!model) throw new Error("Model is not in the Pi catalog");

const weatherTool = {
  name: "get_weather",
  label: "Get Weather",
  description: "Get the current temperature in celsius for a city.",
  parameters: Type.Object({ city: Type.String({ description: "City name" }) }),
  async execute(_toolCallId, params) {
    return {
      content: [{ type: "text", text: `It is 19C in ${params.city}.` }],
      details: { city: params.city, tempC: 19 },
    };
  },
};

// Wrap the agent. piAgentHooks subscribes in place AND returns it — use the result.
const agent = piAgentHooks(
  new Agent({
    initialState: {
      systemPrompt: "You are terse. Use tools when they are relevant.",
      model,
      tools: [weatherTool],
      messages: [],
    },
  }),
);

await agent.prompt("What is the weather in Lisbon? Use the tool.");
await flush();
await shutdown();
```

## What gets captured

One `agent.prompt()` = **one trace**:

```
AGENT  pi_agent.run
 ├─ CHAIN pi_agent.turn.1
 │   ├─ LLM  pi_agent.llm.gpt-4o-mini    ← the tool-calling turn
 │   └─ TOOL pi_agent.tool.get_weather
 └─ CHAIN pi_agent.turn.2
     └─ LLM  pi_agent.llm.gpt-4o-mini    ← the final answer
```

- **LLM spans measure the real provider call.** The span opens on the assistant `message_start` and closes on `message_end`, so its duration is provider latency. Streaming is Pi's default, so `neatlogs.llm.metrics.ttft_ms` (time to first token) is recorded from the first content delta and `neatlogs.llm.is_streaming` reflects whether deltas actually arrived.
- **Cost is exact.** pi-ai prices each call against its own model registry; neatlogs carries `usage.cost.total` through as `neatlogs.llm.cost_usd` rather than re-deriving it from token counts.
- Awaiting `prompt()` waits for that run. `waitForIdle()` is useful when the run was started elsewhere or when queue operations are still active; ensure the agent is idle before the final process-level flush.

## AgentHarness

Pass the maintained harness itself to the same helper:

```typescript
import { AgentHarness } from "@earendil-works/pi-agent-core";

const harness = piAgentHooks(new AgentHarness({ session, models, model, tools }));
await harness.prompt("Investigate this incident");
await harness.navigateTree(targetId, { summarize: true });
await harness.compact();
```

Normal harness prompts use the Agent lifecycle tree. Model-producing `compact()` and
summarizing `navigateTree()` produce `WORKFLOW → CHAIN → LLM`. A navigation with
`summarize: false`, configuration getters/setters, and session/repository operations
perform no model/tool work and therefore do not invent LLM spans.

## Wrapping is idempotent

```typescript
const agent = piAgentHooks(rawAgent);
piAgentHooks(agent); // no-op — never double-subscribes, never double-traces
```

## Multiple agents

Wrap each one. Per-agent state is isolated, so concurrent runs do not bleed into each other:

```typescript
const planner = piAgentHooks(new Agent({ initialState: { systemPrompt: "Plan.", model, tools: [], messages: [] } }));
const worker  = piAgentHooks(new Agent({ initialState: { systemPrompt: "Do.",  model, tools, messages: [] } }));

await Promise.all([planner.prompt("Draft a plan."), worker.prompt("Fetch the data.")]);
```

## Nesting under your own span

Pi's AGENT span parents to whatever neatlogs context is active, so nesting a wrapped agent inside your own `span()` gives you `WORKFLOW → AGENT → CHAIN → LLM/TOOL` in one trace:

```typescript
import { span } from "neatlogs";

const handleRequest = span({ kind: "WORKFLOW", name: "handle_request" }, async () => {
  await agent.prompt(userMessage);
  await agent.waitForIdle();
});

await handleRequest();
```

Do NOT wrap `agent.prompt()` itself in a `span()`/`trace()` of kind AGENT — that duplicates the run span.

## Works with any provider

`piAgentHooks` is provider-agnostic: it reads the model, provider, api, tokens and cost off the assistant message Pi hands it, which is the same shape for every pi-ai provider.

| `getModel(...)` | API key env var |
|---|---|
| `getModel("openai", "gpt-4o-mini")` | `OPENAI_API_KEY` |
| `getModel("anthropic", "claude-haiku-4-5")` | `ANTHROPIC_API_KEY` |
| `getModel("google", "gemini-2.5-flash")` | `GEMINI_API_KEY` / `GOOGLE_API_KEY` |

Pi routes the call through `pi-ai`, not the bare provider SDK, so `piAgentHooks(agent)` is the sole capture point — there is no `wrapOpenAI` step for Pi-routed calls. If the same app ALSO calls a provider SDK **directly** outside Pi, instrument that client explicitly (`const client = wrapOpenAI(new OpenAI())`); it never duplicates Pi spans.

## Verify
1. `await init(...)` runs once at startup, with NO `instrumentations` key.
2. Every `Agent` instance is passed through `piAgentHooks()` and the RETURNED reference is the one called.
3. Each provider used by an agent has its API key in `.env`.
4. The agent is idle before the final `flush()`.
5. If the project uses `agentLoop`/`runAgentLoop`/`streamProxy` instead of the `Agent` class → follow `references/low-level-api.md`.
