# Decorators and Traces Reference — NeatLogs TypeScript SDK

Complete reference for all manual instrumentation APIs in the NeatLogs TypeScript SDK.

---

## 1. `span()` Function Wrapper

The primary manual instrumentation API for custom code. Wraps a function to create an OpenTelemetry span with NeatLogs-specific attributes.

### Signature

```typescript
import { span } from 'neatlogs';
import type { SpanOptions } from 'neatlogs';

const wrapped = span(options: SpanOptions, fn: (...args) => any);
```

### SpanOptions

```typescript
interface SpanOptions {
  kind: SpanKind;           // Required: span kind
  name?: string;            // Span name (defaults to function name)
  description?: string;     // Human-readable description
  captureInput?: boolean;   // Serialize function args (default: true)
  captureOutput?: boolean;  // Serialize return value (default: true)
  mask?: MaskFunction;      // Per-span mask function
  internal?: boolean;       // Mark as internal span
  endUserId?: string;       // End-user id — ONLY honored on a trace ROOT span (see §7)
  endUserMetadata?: Record<string, any>;  // End-user fields (JSON) — root span only

  // Agent-specific
  role?: string;            // AGENT: agent role
  goal?: string;            // AGENT: agent goal

  // Tool-specific
  toolName?: string;        // TOOL/MCP_TOOL: tool name
  parameters?: Record<string, any>;  // TOOL: tool parameters
  toolJsonSchema?: Record<string, any>;  // MCP_TOOL: JSON schema

  // Embedding-specific
  model?: string;           // EMBEDDING: model name
  dimension?: number;       // EMBEDDING: embedding dimension
}
```

> **Note**: Unlike the Python SDK, the TypeScript `SpanOptions` does NOT have `captureStdout`, `tags`, or `version` fields.

### Valid Kinds

`span()` throws an `Error` for any kind not in this set:

`WORKFLOW`, `AGENT`, `CHAIN`, `TOOL`, `RETRIEVER`, `EMBEDDING`, `GUARDRAIL`, `MCP_TOOL`

### When to Use Each Kind

#### WORKFLOW

Top-level entry point that orchestrates the full pipeline.

```typescript
import { span } from 'neatlogs';

const runPipeline = span({ kind: 'WORKFLOW' }, async (topic: string) => {
  const analysis = await researcher(topic);
  const report = await writer(analysis);
  return report;
});
```

#### AGENT

Function representing an AI agent with a specific role/goal.

```typescript
import { span } from 'neatlogs';

const researcher = span(
  { kind: 'AGENT', name: 'researcher', role: 'Research Analyst', goal: 'Find relevant information' },
  async (topic: string) => {
    // ... agent logic with LLM calls ...
    return findings;
  },
);
```

#### CHAIN

Sequential processing step for intermediate processing or pipeline stages.

```typescript
import { span } from 'neatlogs';

const processDocuments = span({ kind: 'CHAIN' }, async (docs: string[]) => {
  return docs.map((d) => d.trim().toLowerCase());
});
```

#### TOOL

Tool/function call (web search, calculator, API call, etc.).

```typescript
import { span } from 'neatlogs';

const webSearch = span(
  { kind: 'TOOL', toolName: 'web_search', description: 'Search the web' },
  async (query: string) => {
    return await searchApi.search(query);
  },
);
```

#### RETRIEVER

RAG retrieval. Automatically extracts documents from the return value.

```typescript
import { span } from 'neatlogs';

const retrieveDocs = span({ kind: 'RETRIEVER' }, async (query: string) => {
  return await vectorDb.search(query, { topK: 5 });
});
```

The RETRIEVER postprocessor automatically:
- Extracts the query from function args named `query`, `question`, or `text`
- Extracts documents from array results or objects with `documents`/`docs`/`results` keys
- Sets `retrieval.documents.N.document.*` attributes (up to 20 docs)

#### EMBEDDING

Embedding generation.

```typescript
import { span } from 'neatlogs';

const embedTexts = span(
  { kind: 'EMBEDDING', model: 'text-embedding-3-small', dimension: 1536 },
  async (texts: string[]) => {
    return await embeddingModel.encode(texts);
  },
);
```

#### GUARDRAIL

Input/output validation and safety checks.

```typescript
import { span } from 'neatlogs';

const checkToxicity = span({ kind: 'GUARDRAIL' }, async (text: string) => {
  const result = await toxicityModel.check(text);
  return { passed: result.score < 0.5, score: result.score };
});
```

#### MCP_TOOL

MCP protocol tool handlers. Automatically wraps string results as `{ result: "..." }` and extracts input from the first argument.

```typescript
import { span } from 'neatlogs';

const getWeather = span(
  { kind: 'MCP_TOOL', toolName: 'get_weather', description: 'Get current weather' },
  async (location: string) => {
    return `Weather in ${location}: Sunny, 72°F`;
  },
);
```

### `captureInput` / `captureOutput`

Default is `true` for both. Set to `false` to suppress serialization — useful for large payloads or sensitive data.

```typescript
const processLargeFile = span(
  { kind: 'CHAIN', captureInput: false, captureOutput: false },
  async (data: Buffer) => { /* ... */ },
);
```

### Complete Multi-Agent Example

```typescript
import { init, span, flush, shutdown } from 'neatlogs';

await init({
  apiKey: '...',
  workflowName: 'research-app',
  instrumentations: ['openai'],
});

const { OpenAI } = await import('openai');
const client = new OpenAI();

const webSearch = span(
  { kind: 'TOOL', toolName: 'web_search' },
  async (query: string) => {
    return `Results for: ${query}`;
  },
);

const researcher = span(
  { kind: 'AGENT', name: 'researcher', role: 'Research Analyst' },
  async (topic: string) => {
    const searchResults = await webSearch(topic);
    const response = await client.chat.completions.create({
      model: 'gpt-4o',
      messages: [{ role: 'user', content: `Analyze: ${searchResults}` }],
    });
    return response.choices[0].message.content;
  },
);

const runPipeline = span({ kind: 'WORKFLOW' }, async (topic: string) => {
  return await researcher(topic);
});

await runPipeline('quantum computing');
await flush();
await shutdown();
```

---

## 2. `Span()` Class Method Decorator

TC39 Stage 3 class-method decorator variant of `span()`. Uses the same `SpanOptions`.

```typescript
import { Span } from 'neatlogs';

class ResearchAgent {
  @Span({ kind: 'AGENT', role: 'researcher' })
  async run(query: string) {
    // ... agent logic ...
    return findings;
  }

  @Span({ kind: 'TOOL', toolName: 'summarize' })
  summarize(text: string) {
    return text.slice(0, 200);
  }
}
```

> **Note**: The `Span()` decorator requires TypeScript 5.0+ with `experimentalDecorators` disabled (TC39 Stage 3 decorators). It is a `ClassMethodDecoratorContext` decorator.

---

## 3. `trace()` Callback Wrapper

For prompt template tracking AND custom span attributes.

### Signature

```typescript
import { trace } from 'neatlogs';
import type { TraceOptions } from 'neatlogs';

const result = await trace(options: TraceOptions, async (span) => {
  // user code runs here with the span active
  return value;
});
```

### TraceOptions

```typescript
interface TraceOptions {
  name: string;                  // Required: span name
  kind?: SpanKind;               // Span kind (default: 'CHAIN')
  promptTemplate?: string | PromptTemplate;   // System prompt template
  promptVariables?: Record<string, any>;      // System prompt variables
  userPromptTemplate?: string | UserPromptTemplate;  // User prompt template
  userPromptVariables?: Record<string, any>;  // User prompt variables
  version?: string;              // Prompt version identifier
  mask?: MaskFunction;           // Per-trace mask function
  endUserId?: string;            // End-user id — ONLY honored on a trace ROOT (see §7)
  endUserMetadata?: Record<string, any>;  // End-user fields (JSON) — root only
  attributes?: Record<string, any>;  // Custom span attributes
}
```

**IMPORTANT**: Unlike `span()`, `trace()` does NOT validate the kind string. It accepts any value including `'LLM'`, `'RERANKER'`, `'VECTOR_STORE'`, etc.

When `kind` is not provided, it defaults to `'CHAIN'`.

### Session-Aware Root Traces

If `sessionId` is set in `init()` AND no active parent span exists, `trace()` creates a NEW root trace (for multi-turn conversations). Otherwise it creates a normal child span.

### Span Object Methods

The `span` parameter in the callback is an OpenTelemetry `Span`. Available methods:

```typescript
await trace({ name: 'my_op', kind: 'CHAIN' }, async (span) => {
  span.setAttribute('key', 'value');        // Add a custom attribute
  span.recordException(error);               // Record an exception
  span.setStatus({ code: SpanStatusCode.ERROR, message: 'msg' });
  span.addEvent('event_name', { key: 'val' });
});
```

### Use Cases for `trace()`

1. **Prompt template tracking** — pass `promptTemplate` / `userPromptTemplate` to capture template + variables on LLM spans
2. **Custom attribute capture** — use `span.setAttribute()` inside the callback
3. **Span kinds not available in `span()`**: `'LLM'`, `'RERANKER'`, `'VECTOR_STORE'`

### Common Anti-Pattern

Do NOT wrap a function that already uses `span({ kind: 'WORKFLOW' })` in `trace()` — it's redundant:

```typescript
// ❌ WRONG: Redundant wrapper
const myWorkflow = span({ kind: 'WORKFLOW' }, async () => { /* ... */ });
await trace({ name: 'main' }, async () => {
  await myWorkflow();  // Already traced by span()
});

// ✅ CORRECT: Just call it directly
await myWorkflow();
```

---

## 4. `log()` — Structured Logging

Capture timestamped log steps within the current trace.

### Signature

```typescript
import { log } from 'neatlogs';

log(msgTemplate: string, options?: Record<string, any>);
```

### Usage

```typescript
import { log } from 'neatlogs';

log('Processing query: {query}', { query: 'What is TypeScript?', level: 'info' });
log('Retrieved {count} documents', { count: 5 });
```

- `msgTemplate` uses `{key}` placeholders (single braces)
- `options` provides template variables and an optional `level` (default: `'info'`)
- Requires `captureLogs: true` in `init()` for OTel LogRecord emission
- In debug mode, logs are echoed to console

---

## 5. Combining `span()` and `trace()` — Prompt Template Pattern

The most common pattern: use `span()` for orchestration and `trace()` inside for prompt tracking.

```typescript
import { init, span, trace, flush, shutdown, PromptTemplate, UserPromptTemplate } from 'neatlogs';

await init({
  apiKey: '...',
  workflowName: 'research',
  instrumentations: ['openai'],
});

const { OpenAI } = await import('openai');
const client = new OpenAI();

const sysTpl = new PromptTemplate('You are a {{role}} assistant. Always be thorough.');
const userTpl = new UserPromptTemplate('Research: {{query}}');

const researcherAgent = span(
  { kind: 'AGENT', name: 'researcher' },
  async (query: string) => {
    return await trace(
      { name: 'research_llm', kind: 'LLM', promptTemplate: sysTpl, userPromptTemplate: userTpl },
      async () => {
        const sysMsg = sysTpl.compile({ role: 'research' }) as string;
        const userMsg = userTpl.compile({ query }) as string;
        const response = await client.chat.completions.create({
          model: 'gpt-4o',
          messages: [
            { role: 'system', content: sysMsg },
            { role: 'user', content: userMsg },
          ],
        });
        return response.choices[0].message.content;
      },
    );
  },
);
```

---

## 6. Custom Span Attributes via `trace()`

### RERANKER

```typescript
import { trace } from 'neatlogs';

async function rerank(query: string, docs: string[], topN = 3) {
  return await trace({ name: 'rerank', kind: 'RERANKER' }, async (span) => {
    span.setAttribute('neatlogs.reranker.query', query);
    span.setAttribute('neatlogs.reranker.top_k', topN);
    span.setAttribute('neatlogs.reranker.model_name', 'cohere-rerank-v3');
    span.setAttribute('neatlogs.reranker.input_documents', JSON.stringify(docs));
    const reranked = await rerankerModel.rerank(query, docs, topN);
    span.setAttribute('neatlogs.reranker.output_documents', JSON.stringify(reranked));
    return reranked;
  });
}
```

### VECTOR_STORE

```typescript
import { trace } from 'neatlogs';

async function vectorSearch(query: string, topK = 10) {
  return await trace({ name: 'vector_search', kind: 'VECTOR_STORE' }, async (span) => {
    span.setAttribute('neatlogs.vector_store.query', query);
    span.setAttribute('neatlogs.vector_store.top_k', topK);
    const results = await vectorDb.search(query, topK);
    span.setAttribute('neatlogs.vector_store.result_count', results.length);
    return results;
  });
}
```

### Manual LLM Span (No SDK to Patch)

When calling an LLM API directly over raw HTTP (`fetch`/`undici`/`axios`) without an instrumented SDK — the wrappers (`wrapOpenAI`, …) are BLIND to these. **Non-streaming** uses the `trace()` callback:

```typescript
import { trace } from 'neatlogs';

async function rawLlmCall(prompt: string) {
  return await trace({ name: 'raw_api_llm_call', kind: 'LLM' }, async (span) => {
    span.setAttribute('neatlogs.internal', false);  // Required: no auto-instrumented sibling
    span.setAttribute('neatlogs.llm.model_name', 'gpt-4o');
    span.setAttribute('neatlogs.llm.input', JSON.stringify({ messages: [{ role: 'user', content: prompt }] }));

    const response = await fetch('https://api.openai.com/v1/chat/completions', {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${apiKey}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ model: 'gpt-4o', messages: [{ role: 'user', content: prompt }] }),
    });
    const data = await response.json();

    span.setAttribute('neatlogs.llm.output', JSON.stringify({ role: 'assistant', content: data.choices?.[0]?.message?.content ?? '' }));
    span.setAttribute('neatlogs.llm.token_count.prompt', data.usage.prompt_tokens);
    span.setAttribute('neatlogs.llm.token_count.completion', data.usage.completion_tokens);
    span.setAttribute('neatlogs.llm.token_count.total', data.usage.total_tokens);
    return data;
  });
}
```

> **Important**: Set `neatlogs.internal` to `false` on manual LLM spans when there's no auto-instrumented sibling. Otherwise the backend drops the span.

> **Streaming raw HTTP** can't use the `trace()` callback (it closes the span when the callback returns, but a stream yields over time). Use the manual `startSpan()`/`end()` lifecycle and the per-provider field paths — see **`references/raw-http-llm.md`**.

---

## 7. End-User Identity (`endUserId` / `endUserMetadata`)

Attaches the **end-user** — the user of YOUR application (the person using your AI product) — to a trace, so you can filter the traces page by end-user and power per-user analytics.

> Distinct from `init({ userId })`, which identifies the *operator* running the SDK (a developer, a service account). Setting one does not set the other.

### The model: one end-user per trace; end-user is session-level

- A trace belongs to exactly **one** end-user — declared once, no per-span override, no `identify()` call.
- It is effectively **session-level**: a multi-turn chat (`init({ autoSession: true })` or an explicit `sessionId`) is one session with many traces, all the same person. A plain workflow is one trace = one session. The backend rolls the value up from the trace to its session.

### Where to set it — only on the trace ROOT (or init)

The SDK only honors `endUserId` on the **root span** of a trace (any kind). On a non-root child span it is **silently ignored**.

| Case | How | Notes |
|------|-----|-------|
| 1. Root is a `span()` wrapper | `span({ kind: 'WORKFLOW', endUserId }, fn)` | The wrapped fn must be the trace root (no active parent). |
| 2. Root is a `trace()` block | `trace({ name: 'chat', endUserId }, async () => {...})` | The top-level `trace()` at a request/turn boundary. |
| 3. Auto-root via `wrapOpenAI`/etc. only | `init({ endUserId })` | Process-global default landing on the auto-created root. Single-user processes only. |
| 4. Non-root child span | — | **Ignored.** Move it to the root. |

### Multi-tenant server (the common case)

Read the id from the per-request context and set it on the root you open at the handler — never hardcode it:

```typescript
app.post('/chat', async (req, res) => {
  // req.user.id differs per request — resolve it HERE.
  const out = await trace(
    { name: 'chat', endUserId: String(req.user.id), endUserMetadata: { plan: req.user.plan } },
    async () => runAgent(req.body.message),   // children inherit nothing extra — the root carries the id
  );
  res.json(out);
});
```

For a multi-turn chat, also set `sessionId` (or `autoSession: true`) so the per-turn traces group under one session; set `endUserId` on each turn's root (same value every turn).

### Browser SDK

In `neatlogs/browser`, set the end-user once on the client (`new Neatlogs({ apiKey, endUser, endUserMetadata })`) or per call (`trackAI({ ..., endUser })` / `trace({ ..., endUser })`). It is attached to the trace root only.

### Single-user process (CLI / worker)

```typescript
await init({ apiKey: ..., workflowName: 'batch', endUserId: 'u_812' });
// Every trace in this process is attributed to u_812 (lands on the root via a resource attribute).
```
