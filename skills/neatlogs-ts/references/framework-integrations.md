# Framework Integrations — NeatLogs TypeScript SDK Reference

Framework-specific integration patterns for the NeatLogs TypeScript SDK. Covers the wrapper for each supported LLM provider and agent framework, plus representative code examples.

> **`init({ instrumentations: [...] })` THROWS for every provider/framework key.** Instrumentation is always an explicit helper applied to the object — see [Supported Instrumentations](../SKILL.md#supported-instrumentations). Because helpers patch the **instance**, not the module, import order never matters.

---

## 1. Integration Approaches (Decision Tree)

### 1a. Wrapper Only

For applications that call LLM providers directly. Wrap the client; its calls are traced and a `WORKFLOW` root opens automatically.

```typescript
import { init, wrapOpenAI } from 'neatlogs';
import { OpenAI } from 'openai';

await init({ apiKey: process.env.NEATLOGS_API_KEY });
const client = wrapOpenAI(new OpenAI());
```

### 1b. Wrapper + `span()` Wrappers

For custom multi-agent orchestration. Wrap each provider client, then use `span()` on your orchestration functions so everything nests under one root.

```typescript
import { init, wrapOpenAI, wrapAnthropic, span } from 'neatlogs';
import { OpenAI } from 'openai';
import { Anthropic } from '@anthropic-ai/sdk';

await init({ apiKey: process.env.NEATLOGS_API_KEY });
const openaiClient = wrapOpenAI(new OpenAI());
const anthropicClient = wrapAnthropic(new Anthropic());

const pipeline = span({ kind: 'WORKFLOW' }, async (query: string) => {
  const resultA = await agentA(query);
  const resultB = await agentB(resultA);
  return resultB;
});
```

### 1c. Manual LLM spans only when no integration owns the call

Do not wrap provider/framework calls in `trace({ kind: 'LLM' })` after applying their wrapper, handler, hook, or processor. That capture layer already owns the canonical LLM span. Use a manual LLM trace only for an unsupported SDK or raw HTTP request, and populate its model, input, output, usage, status, and errors yourself.

---

## 2. OpenAI

- **Wrapper**: `wrapOpenAI(client)` from `neatlogs` (or `neatlogs/openai`)
- **Import order**: irrelevant — the wrapper patches the instance
- **Supports**: sync, async (`AsyncOpenAI`-style usage), streaming
- **Auto-roots**: yes — a lone wrapped call opens its own `WORKFLOW` root

```typescript
import { init, wrapOpenAI, span, flush, shutdown } from 'neatlogs';
import { OpenAI } from 'openai';

await init({
  apiKey: '...',
  workflowName: 'my-app',
});

const client = wrapOpenAI(new OpenAI());

const run = span({ kind: 'WORKFLOW' }, async (query: string) => {
  const response = await client.chat.completions.create({
    model: 'gpt-4o',
    messages: [{ role: 'user', content: query }],
  });
  return response.choices[0].message.content;
});

await run('Explain quantum computing');
await flush();
await shutdown();
```

---

## 3. Anthropic

- **Wrapper**: `wrapAnthropic(client)` from `neatlogs` (or `neatlogs/anthropic`)
- **Supports**: extended thinking, streaming, tool use
- **Auto-roots**: yes

```typescript
import { init, wrapAnthropic, span, flush, shutdown } from 'neatlogs';
import { Anthropic } from '@anthropic-ai/sdk';

await init({
  apiKey: '...',
  workflowName: 'anthropic-app',
});

const client = wrapAnthropic(new Anthropic());

const analyst = span(
  { kind: 'AGENT', name: 'analyst' },
  async (query: string) => {
    const response = await client.messages.create({
      model: 'claude-sonnet-4-6',
      max_tokens: 1024,
      system: 'You are a market analysis expert.',
      messages: [{ role: 'user', content: query }],
    });
    return response.content[0].text;
  },
);

await analyst('Analyze market trends');
await flush();
await shutdown();
```

---

## 4. LangChain

- **Helper**: `langchainHandler()` from `neatlogs` (or `neatlogs/langchain`)
- **Captures**: LLM calls, chains, agents, tools, retrievers
- **Auto-roots**: yes — the handler opens a root per run

Pass the handler in `config.callbacks` at the **model/chain level** (inside your nodes), not on `graph.invoke()`:

```typescript
import { init, langchainHandler, span, flush, shutdown } from 'neatlogs';
import { ChatOpenAI } from '@langchain/openai';

await init({
  apiKey: '...',
  workflowName: 'langchain-app',
});

const handler = langchainHandler();
const llm = new ChatOpenAI({ model: 'gpt-4o' });

const runAgent = span({ kind: 'WORKFLOW' }, async (query: string) => {
  const response = await llm.invoke(query, { callbacks: [handler] });
  return response.content;
});

await runAgent('Explain black holes');
await flush();
await shutdown();
```

For LangGraph specifics, use the dedicated `neatlogs-ts-langchain` skill.

---

## 5. AWS Bedrock

- **Wrapper**: `wrapBedrock(client)` from `neatlogs/bedrock`
- **Covers**: `ConverseCommand`, `ConverseStreamCommand`, `InvokeModelCommand` (patches `client.send`)
- **Auto-roots**: yes

```typescript
import { init, span, flush, shutdown } from 'neatlogs';
import { wrapBedrock } from 'neatlogs/bedrock';
import { BedrockRuntimeClient, ConverseCommand } from '@aws-sdk/client-bedrock-runtime';

await init({
  apiKey: '...',
  workflowName: 'bedrock-app',
});

const bedrockClient = wrapBedrock(new BedrockRuntimeClient({ region: 'us-east-1' }));

const run = span({ kind: 'WORKFLOW' }, async (prompt: string) => {
  return await bedrockClient.send(new ConverseCommand({ /* ... */ }));
});

await run('Hello');
await flush();
await shutdown();
```

---

## 6. MCP (Model Context Protocol)

- **No auto-instrumentor** — `instrumentations: ['mcp']` throws. Instrument MCP tools yourself with `span({ kind: 'MCP_TOOL' })`.

```typescript
import { init, span, flush, shutdown } from 'neatlogs';

await init({
  apiKey: '...',
  workflowName: 'mcp-app',
});

// Give each MCP tool handler an MCP_TOOL span:
const getWeather = span(
  { kind: 'MCP_TOOL', toolName: 'get_weather', toolJsonSchema: { type: 'object', properties: { location: { type: 'string' } } } },
  async (location: string) => {
    return `Weather in ${location}: Sunny, 72°F`;
  },
);
```

---

## 7. Claude Agent SDK

- **Wrapper**: `wrapClaudeAgentSDK(sdk)` from `neatlogs/claude-agent-sdk`
- **Wraps** the module's `query`; every other export (`createSdkMcpServer`, `tool`, …) passes through unchanged

```typescript
import { init, flush, shutdown } from 'neatlogs';
import { wrapClaudeAgentSDK } from 'neatlogs/claude-agent-sdk';
import * as claudeSdk from '@anthropic-ai/claude-agent-sdk';

await init({
  apiKey: '...',
  workflowName: 'claude-agent-app',
});

// Use the wrapped module's query() — the raw import is NOT traced.
const { query } = wrapClaudeAgentSDK(claudeSdk);

for await (const message of query({ prompt: 'Summarize this repo' })) {
  // ...
}

await flush();
await shutdown();
```

---

## 8. BeeAI

- **No auto-instrumentor** — `instrumentations: ['beeai']` throws. Instrument your BeeAI agent/tool functions with `span()` (`kind: 'AGENT'` / `'TOOL'`), and the underlying provider client with its own wrapper.

```typescript
import { init, wrapOpenAI, span, flush, shutdown } from 'neatlogs';
import { OpenAI } from 'openai';

await init({
  apiKey: '...',
  workflowName: 'beeai-app',
});

const client = wrapOpenAI(new OpenAI());

const runAgent = span({ kind: 'AGENT', name: 'bee_agent' }, async (task: string) => {
  // ... your BeeAI code, using the wrapped client ...
});

await flush();
await shutdown();
```

---

## 9. Mastra

- **Wrapper**: `wrapMastra(entity)` from `neatlogs/mastra` (no extra package needed)

Wrap each Mastra entity with `wrapMastra` — it patches Agent/Workflow/Vector/Memory methods to emit spans. Init once at startup, before constructing entities:

```typescript
import { init } from 'neatlogs';
import { wrapMastra } from 'neatlogs/mastra';
import { Agent } from '@mastra/core/agent';
import { openai } from '@ai-sdk/openai';

await init({ apiKey: '...', workflowName: 'mastra-app' });

const agent = wrapMastra(
  new Agent({ name: 'assistant', instructions: 'Be concise.', model: openai('gpt-4o') }),
);
```

Mastra agent, workflow, tool, and LLM step spans are automatically captured.

> **`getMastraObservability()` is deprecated and now throws.** Its native-observability bridge activates spans on the global OpenTelemetry context, which can't be isolated from co-tenant tracing SDKs. Use `wrapMastra()` instead.

---

## 10. Vercel AI SDK (`ai` package)

- **Import**: `import { wrapAISDK } from 'neatlogs/ai'` (built into the SDK, no separate package)
- **Compatibility**: `ai >=3 <7` (v3, v4, v5, v6)
- **No monkey-patching**: the AI SDK supports OpenTelemetry natively via `experimental_telemetry`. The wrapper opts in per call site, so there's no fragile module patching.

> **Two APIs**: use `wrapAISDK(ai)` for the ergonomic wrapper (recommended), or `createAITelemetry()` for direct `experimental_telemetry` injection on individual calls.

### Recommended: `wrapAISDK`

```typescript
import { init, flush, shutdown } from 'neatlogs';
import { wrapAISDK } from 'neatlogs/ai';
import * as ai from 'ai';
import { openai } from '@ai-sdk/openai';

// 1. Initialize neatlogs first (sets up its private TracerProvider — never registered globally)
await init({ apiKey: '...', workflowName: 'ai-sdk-app' });

// 2. Wrap the ai module — wraps generateText, streamText, generateObject, streamObject, embed, embedMany, rerank
const { generateText, streamText, generateObject, streamObject, embed, embedMany, rerank } = wrapAISDK(ai);

// 3. Use the wrapped functions exactly like the originals
const { text } = await generateText({
  model: openai('gpt-4o-mini'),
  prompt: 'What is the capital of France?',
});

await flush();
await shutdown();
```

Each wrapped call:
1. Opens a parent OTel span on the active `TracerProvider` with `openinference.span.kind = 'WORKFLOW'` (for generateText/streamText/generateObject/streamObject) or `'CHAIN'` (for embed/embedMany/rerank). The AI SDK's native `ai.doGenerate` / `ai.doStream` child spans remain `LLM`; tool-call children remain `TOOL`.
2. Forces `experimental_telemetry: { isEnabled: true, recordInputs: true, recordOutputs: true, tracer, metadata: { neatlogsWrapped: true } }` for that call. **`isEnabled: false` is overridden** — to skip telemetry for a specific call, use the unwrapped `ai` import directly.
3. Captures `input.value` (always) and `output.value`. For `generateText`/`generateObject` this is the awaited result; for `streamText`/`streamObject` it's captured from the AI SDK's `onFinish` callback (with `gen_ai.finish_reason`), preserving any user-provided `onFinish`/`onError`. `generateObject`/`streamObject` structured output (`ai.response.object`) maps to the LLM child's output.
4. Sets `SpanStatusCode.ERROR` on rethrown exceptions.

### Lower-level: `createAITelemetry`

When you want telemetry on a single call without wrapping the whole module:

```typescript
import { generateText } from 'ai';
import { openai } from '@ai-sdk/openai';
import { createAITelemetry } from 'neatlogs/ai';

await generateText({
  model: openai('gpt-4o-mini'),
  prompt: 'Hello',
  experimental_telemetry: createAITelemetry({ metadata: { userId: 'u-123' } }),
});
```

### Captured attributes (after pipeline normalization)

The Vercel AI SDK emits its own `ai.*` namespace; the SDK's `UnifiedAttributeProcessor` maps these to `neatlogs.*`:

| AI SDK attribute | Neatlogs attribute |
|------------------|--------------------|
| `ai.model.id` | `neatlogs.llm.model_name` |
| `ai.model.provider` | `neatlogs.llm.provider` |
| `ai.usage.promptTokens` | `neatlogs.llm.token_count.prompt` |
| `ai.usage.completionTokens` | `neatlogs.llm.token_count.completion` |
| `ai.usage.totalTokens` | `neatlogs.llm.token_count.total` |
| `ai.prompt.messages` (JSON array) | `neatlogs.llm.input_messages.{i}.{role,content}` |
| `ai.response.text` | `neatlogs.llm.output_messages.0.content` |
| `ai.response.toolCalls` (JSON array) | `neatlogs.llm.tool_calls.{i}.{name,arguments,id}` |
| `ai.toolCall.name` / `args` / `result` | `tool.name` / `input.value` / `output.value` (on `ai.toolCall` spans) |
| `ai.settings.{temperature,maxTokens,topP,…}` | `neatlogs.llm.{temperature,max_tokens,top_p,…}` |

### Note on `init({ instrumentations: ['ai_sdk'] })`

`ai_sdk` exists in the instrumentation registry for scope-detection consistency, but passing it to `init()` **throws** (its registry entry names an instrumentor module, so the isolation gate rejects it). `wrapAISDK(ai)` is the only path.

---

## 11. Long-Running Servers (Express, Fastify, etc.)

For server applications, `init()` is called **once at startup**. Do NOT call `flush()` or `shutdown()` on every request.

```typescript
import { init, wrapOpenAI, span, flush, shutdown } from 'neatlogs';
import { OpenAI } from 'openai';
import express from 'express';

await init({
  apiKey: '...',
  workflowName: 'my-api',
});

const client = wrapOpenAI(new OpenAI());

const app = express();

app.get('/ask', async (req, res) => {
  const askWorkflow = span({ kind: 'WORKFLOW', name: 'ask_workflow' }, async (q: string) => {
    const response = await client.chat.completions.create({
      model: 'gpt-4o',
      messages: [{ role: 'user', content: q }],
    });
    return response.choices[0].message.content;
  });

  const answer = await askWorkflow(req.query.q as string);
  res.json({ answer });
  // DO NOT call flush() here
});

// Graceful shutdown
process.on('SIGTERM', async () => {
  await flush();
  await shutdown();
  process.exit(0);
});

app.listen(3000);
```

> **Key difference from Python**: In TypeScript, `flush()` and `shutdown()` are already async — just `await` them directly. No need for thread delegation.
