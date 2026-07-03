---
name: neatlogs-ts
description: >
  NeatLogs is an AI agent debugging and observability platform. Use this skill when
  instrumenting TypeScript/Node.js LLM applications with neatlogs for tracing, monitoring,
  debugging, observability, spans, prompt template tracking, or auto-instrumentation of
  LLM providers and agent frameworks.
---

# NeatLogs TypeScript SDK — Agent Skill

NeatLogs auto-instruments LLM calls, agent frameworks, and custom code with these core exports:
`init()`, `flush()`, `shutdown()`, `span()`, `Span()`, `trace()`, `identify()`, `log()`, `PromptTemplate`, and `UserPromptTemplate`.

---

## Installation

Always install the latest published version (don't pin an older one):

```bash
npm install neatlogs@latest
# pnpm add neatlogs@latest · yarn add neatlogs@latest · bun add neatlogs@latest
```

Requires Node.js >= 18.

---

## Core Principles

1. **Import order matters**: `await init()` MUST be called **before** importing any LLM libraries (OpenAI, Anthropic, etc.) for auto-instrumentation patching to work. Use dynamic `import()` for LLM libraries after init.
2. **Scripts**: end with `await flush()` then `await shutdown()`. **Servers**: call `init()` once at startup; do NOT call `flush()` or `shutdown()` on every request.
3. **Use `span()` wrappers** for custom code; use `trace()` callback wrapper for prompt template tracking or custom attributes.
4. **Prefer auto-instrumentation** (`instrumentations: ['openai']`) over manual wrapping when possible.
5. **Init is single-shot**: `init()` configures the global telemetry provider. Calling it again is a no-op (with a warning). Call `shutdown()` first to reinitialize (rare).
6. **All lifecycle functions are async**: `init()`, `flush()`, and `shutdown()` return Promises and must be awaited.
7. **Named imports**: Always use named imports from `'neatlogs'`.

---

## Quick Start

Complete minimal working example:

```typescript
import { init, span, flush, shutdown } from 'neatlogs';

await init({
  apiKey: process.env.NEATLOGS_API_KEY ?? '',
  workflowName: 'my-app',
  instrumentations: ['openai'],
});

// NOW import the LLM library (after init)
const { OpenAI } = await import('openai');

const client = new OpenAI();

const myWorkflow = span({ kind: 'WORKFLOW' }, async (query: string) => {
  const response = await client.chat.completions.create({
    model: 'gpt-4o',
    messages: [{ role: 'user', content: query }],
  });
  return response.choices[0].message.content;
});

await myWorkflow('Hello!');
await flush();
await shutdown();
```

---

## Instrumentation Workflow

1. **Assess**: Detect what LLM providers/frameworks the project uses.
2. **Instrument**: Choose the correct approach:
   - Auto-instrumentation for providers → add to `instrumentations: []`
   - `span()` wrappers for custom orchestration code
   - `trace()` for prompt template tracking or custom span attributes
3. **Init**: Add `await init()` **BEFORE** any LLM library dynamic imports with the correct `instrumentations` list.
4. **Verify**: Check the NeatLogs dashboard for incoming traces.

---

## `init()` Reference

```typescript
import { init } from 'neatlogs';
await init(options);
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `apiKey` | `string` | `undefined` | API key (or set `NEATLOGS_API_KEY` env var). If neither is set, spans are created locally but **silently not exported** |
| `workflowName` | `string` | derived from `process.argv[1]` | Name for this workflow/application |
| `instrumentations` | `string[]` | `undefined` | Libraries to auto-instrument (e.g. `['openai', 'langchain']`) |
| `tags` | `string[]` | `undefined` | Tags for filtering in dashboard |
| `userId` | `string` | `undefined` | The **operator** running the SDK (developer / service account), NOT your app's end-user. For end-user & session identity, see **Sessions & End-Users** below |
| `sampleRate` | `number` | `1.0` | Sampling rate (0.0 to 1.0) |
| `flushInterval` | `number` | `5` | Seconds between batch flushes |
| `batchSize` | `number` | `100` | Max spans per batch |
| `debug` | `boolean` | `false` | Enable verbose logging |
| `disableExport` | `boolean` | `false` | Disable span export to backend |
| `captureLogs` | `boolean` | `false` | Capture `log()` calls as LOG spans |
| `traceContent` | `boolean` | `true` | Whether to capture input/output content |
| `pii` | `'redact' \| 'hash' \| false` | `undefined` | PII detection setting |
| `piiEnabled` | `boolean` | `undefined` | Override team-level server-side PII redaction |
| `piiSpanTypes` | `string[]` | `undefined` | Override which span types have PII redaction |
| `mask` | `MaskFunction` | `undefined` | Client-side mask function |
| `metadata` | `Record<string, any>` | `undefined` | Custom metadata to attach to all spans |
| `endpoint` | `string` | `'https://ingest.neatlogs.com'` | Backend endpoint URL |
| `baseUrl` | `string` | `undefined` | Base URL for the Neatlogs API |

---

## Sessions & End-Users

Track **your app's end-users** and group a conversation's turns so you can analyze usage/cost/errors per customer & segment, view multi-turn timelines, and do per-customer replay.

Model: **one turn = one trace**; a **session** groups the turns of a conversation (pass the same `sessionId` on every turn). The end-user is per session. Identity is stamped on the **trace ROOT only** — the backend rolls it up; child spans ignore these fields. `init()` does **not** accept any session/end-user param.

Three ways to declare identity (per-request):

```typescript
// 1. On a trace() root
await trace({ name: 'turn', sessionId: 'conv_123', endUserId: 'u_456', endUserMetadata: { plan: 'pro' } }, async () => { /* ... */ });

// 2. On a span() root
span({ kind: 'WORKFLOW', sessionId: 'conv_123', endUserId: 'u_456', endUserMetadata: { plan: 'pro' } }, fn);

// 3. Wrapper-only code (no root of your own — you only call neatlogs.wrap(...))
await identify({ sessionId: 'conv_123', endUserId: 'u_456', endUserMetadata: { plan: 'pro' } }, async () => {
  await client.chat.completions.create(/* ... */); // the wrapper's auto-root inherits the identity (framework wrappers too, on recent versions)
});
```

> **Browser SDK** (`neatlogs/browser`) uses the same field names — `endUserId`, `endUserMetadata`, `sessionId` — as client-constructor defaults or per-call on `trace()` / `trackAI()`.

---

## Supported Instrumentations

Pass these string values in the `instrumentations` array to `init()`.

### Working Instrumentations (TS SDK v1)

| Key | Library | Package |
|---|---|---|
| `openai` | OpenAI | `@arizeai/openinference-instrumentation-openai` |
| `anthropic` | Anthropic | `@arizeai/openinference-instrumentation-anthropic` |
| `langchain` | LangChain | `@arizeai/openinference-instrumentation-langchain` |
| `bedrock` | AWS Bedrock | `@arizeai/openinference-instrumentation-bedrock` |
| `mcp` | Model Context Protocol | `@arizeai/openinference-instrumentation-mcp` |
| `beeai` | BeeAI | `@arizeai/openinference-instrumentation-beeai` |
| `claude_agent_sdk` | Claude Agent SDK | `@arizeai/openinference-instrumentation-claude-agent-sdk` |
| `mastra` | Mastra | `@neatlogs/instrumentation-mastra` (custom) |
| `google_genai` | Google GenAI (`@google/genai`) | `@neatlogs/instrumentation-google-genai` (custom) |
| `ai_sdk` | Vercel AI SDK (`ai`) | Built into `neatlogs/ai` (opt-in via `wrapAISDK(ai)`) |

> **Explicit client wrappers** (alternative to the instrumentation key, mirroring Python's `neatlogs.wrap()`): `wrapGoogleGenAI` from `neatlogs/google-genai` (Gemini / AI Studio, `provider=google`) and `wrapVertexAI` from `neatlogs/vertex-ai` (Vertex mode, `provider=vertex_ai`) for `@google/genai` clients. Use the wrapper OR the `google_genai` instrumentation key — not both.

### Registered but Not Instrumentable (TS SDK v1)

These are in the registry but have `null` instrumentation fields — they cannot be auto-instrumented in the current TypeScript SDK version:

`litellm`, `crewai`

> **HTTP auto-instrumentation** (fetch/undici) is always enabled by `init()` for trace context propagation — you do not need to list it in `instrumentations`.

---

## Reference Docs

For deep dives, see the companion reference files:

- **Custom instrumentation** with `span()`, `Span()`, and `trace()` → [`references/decorators-and-traces.md`](references/decorators-and-traces.md)
- **Raw HTTP LLM calls** (fetch/undici/axios — wrappers are BLIND, need manual spans; streaming lifecycle + per-provider field paths) → [`references/raw-http-llm.md`](references/raw-http-llm.md)
- **Prompt template** tracking and management → [`references/prompt-templates.md`](references/prompt-templates.md)
- **Framework-specific** integration patterns → [`references/framework-integrations.md`](references/framework-integrations.md)
- **Troubleshooting** and common mistakes → [`references/troubleshooting.md`](references/troubleshooting.md)

---

## Environment Variables

| Variable | Description |
|---|---|
| `NEATLOGS_API_KEY` | API key (alternative to `apiKey` param) |
| `NEATLOGS_DISABLE_EXPORT` | Set to `"true"` to disable span export |
| `NEATLOGS_TRACE_CONTENT` | Set to `"false"` to disable input/output capture |

---

## Data Masking and PII

NeatLogs supports both client-side and server-side PII redaction.

### Client-Side Masking

Provide a `mask` callback to `init()` to redact sensitive data before spans leave the process. You can also pass `mask` per-span via `span({ mask: fn })` or `trace({ mask: fn })`.

```typescript
import { init } from 'neatlogs';
import type { MaskFunction } from 'neatlogs';

const redactPii: MaskFunction = (spanData) => {
  for (const key of Object.keys(spanData)) {
    if (key.includes('email') || key.includes('password')) {
      spanData[key] = '[REDACTED]';
    }
  }
  return spanData;
};

await init({ mask: redactPii });
```

### Server-Side PII Redaction

Enable automatic server-side redaction:

```typescript
await init({
  piiEnabled: true,
});
```

---

## Documentation

Full documentation: [https://docs.neatlogs.com/](https://docs.neatlogs.com/)
