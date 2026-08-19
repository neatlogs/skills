---
name: neatlogs-ts
description: >
  NeatLogs is an AI agent debugging and observability platform. Use this skill when
  instrumenting TypeScript/Node.js LLM applications with neatlogs for tracing, monitoring,
  debugging, observability, spans, or instrumentation of
  LLM providers and agent frameworks.
---

# NeatLogs TypeScript SDK — Agent Skill

NeatLogs auto-instruments LLM calls, agent frameworks, and custom code with these core exports:
`init()`, `flush()`, `shutdown()`, `span()`, `Span()`, `trace()`, `identify()`, and `log()`.

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

1. **Import order does NOT matter**: instrumentation is per-instance via a `wrap*` helper (`wrapOpenAI(new OpenAI())`), so static top-of-file imports are fine. No dynamic `import()` gymnastics.
2. **Scripts**: end with `await flush()` then `await shutdown()`. **Servers**: call `init()` once at startup; do NOT call `flush()` or `shutdown()` on every request.
3. **One capture owner per operation**: a provider/framework wrapper, handler, hook, or processor owns the spans for calls it captures. Use `span()` for your own orchestration. Use `trace()` for custom attributes or a manual LLM span only when no supported capture layer owns that operation.
4. **Managed endpoint is automatic**: omit `endpoint`, `baseUrl`, and `NEATLOGS_ENDPOINT`; the SDK already exports to `https://ingest.neatlogs.com`. Preserve an explicit endpoint only for a confirmed self-hosted deployment.
4. **NEVER pass `instrumentations: [...]` for a provider or framework — `init()` THROWS.** Every provider/framework key (`openai`, `anthropic`, `langchain`, `bedrock`, `mcp`, `beeai`, `claude_agent_sdk`, `google_genai`, `mastra`, `ai_sdk`, `azure_openai`, `vertexai`, `openrouter_agent`, `opencode`) is rejected because its auto-instrumentor drives the **global** OTel context and cannot be isolated. Use the explicit helper from the [Supported Instrumentations](#supported-instrumentations) table.
5. **Init is single-shot**: `init()` configures a **private** telemetry provider (never registered globally — see [OTel Isolation](#otel-isolation)). Calling it again is a no-op (with a warning). Call `shutdown()` first to reinitialize (rare).
6. **All lifecycle functions are async**: `init()`, `flush()`, and `shutdown()` return Promises and must be awaited.
7. **Named imports**: Always use named imports from `'neatlogs'`.

### Transport selection

Use this SDK for TypeScript/Node.js. Neatlogs also has SDKs for Python and Go. For a language without a supported Neatlogs SDK, default to the dependency-free HTTP ingest endpoint `POST /v1/trace`; if that project already emits OpenTelemetry, OTLP/gRPC is also supported. Use the `neatlogs-ingest` skill for the complete HTTP and gRPC contracts. Do not confuse `/v1/trace` nested JSON with the `/v1/traces` OTLP/HTTP protobuf route.

---

## Quick Start

Complete minimal working example:

```typescript
import { init, wrapOpenAI, span, flush, shutdown } from 'neatlogs';
import { OpenAI } from 'openai';

await init({
  apiKey: process.env.NEATLOGS_API_KEY ?? '',
  workflowName: 'my-app',
});

// wrapOpenAI patches THIS instance — import order is irrelevant.
const client = wrapOpenAI(new OpenAI());

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
   - Providers/frameworks → the matching `wrap*` helper / handler / processor (see [Supported Instrumentations](#supported-instrumentations))
   - `span()` wrappers for custom orchestration code
   - `trace()` for custom span attributes and unsupported/raw operations only—never around a call already owned by a wrapper, handler, hook, processor, or instrumentor
3. **Init**: Add `await init()` once at startup, with **no** `instrumentations` key.
4. **Verify**: build/typecheck the changed project, restart any server/startup process, exercise the real instrumented path, and confirm a new NeatLogs trace with one canonical span per operation.

For a generic Next.js retrieval-and-generation example, see [Retrieval-and-generation workflow verification](references/retrieval-generation-workflow.md).

## Completion gate

- Show concise progress for install, edits, build, restart, runtime verification, and platform confirmation; never print secrets.
- Run the project's existing build/typecheck/test commands after editing. Restart long-running processes so new startup instrumentation is actually loaded.
- Exercise a safe representative path and confirm its trace reaches the target project. This skill does not grant platform access. The marker-aware `get_trace_context` contract must be deployed on the hosted Neatlogs backend; a merged backend change or updated local wizard alone is not proof.
- For the representative run, generate a UUID and append `neatlogs.verification.marker=<UUID>` to `OTEL_RESOURCE_ATTRIBUTES`, preserving existing entries. Scope it only to the launched process: do not edit source or persistent configuration, and do not treat the marker as a secret. Immediately before exercising the real path, record the current UTC timestamp. If the coding agent cannot launch a web UI path, tell the user exactly how to start the app with that temporary environment value, then continue verification against the same marker.
- After the run, call the already-connected Neatlogs platform MCP's existing `get_trace_context(verification_marker=<same UUID>)` directly; make no preliminary MCP discovery calls and never fall back to the latest trace if the marker is absent; report that exact blocker and leave verification incomplete. While `status` is `processing` or `finalization_status` is `pending`, poll the same trace with `get_trace_context(trace_id=<trace_id>)`. Only after `finalization_status` is `finalized`, page with `get_trace_context(trace_id=<trace_id>, offset=<next_offset>)` until `next_offset` is null, and verify that all `span_count` spans were inspected.
- If `get_trace_context` rejects `verification_marker`, `trace_id`, or `offset`, or omits `status`, `finalization_status`, `next_offset`, or `span_count`, treat the hosted MCP as an old contract: stop, report the hosted deployment blocker, and do not claim verification or use another trace query.
- If MCP is unavailable, ask the user to configure `https://ingest.neatlogs.com/mcp` (or `npx @neatlogs/wizard mcp --api-key <PROJECT_KEY>`) in the coding agent and store the project key as a client secret. Never print or request it in chat; leave verification incomplete if access cannot be established.
- Do not claim success from source inspection or an offline/no-export check. Inspect the full persisted span tree and canonical attributes, not only a trace-list summary or local debug output. Confirm the marker-matched project trace is the fresh run, with one span per semantic operation and no duplicates. If live ingestion cannot be confirmed, report the exact blocker and leave the result incomplete.

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
| `instrumentations` | `string[]` | `undefined` | **Do not use.** `init()` THROWS for every provider/framework key — see [Core Principles](#core-principles) #4 and [Why the instrumentations key throws](#why-the-instrumentations-key-throws) |
| `tags` | `string[]` | `undefined` | Tags for filtering in dashboard |
| `userId` | `string` | `undefined` | The **operator** running the SDK (developer / service account), NOT your app's end-user. For end-user & session identity, see [Sessions & End-Users](#sessions--end-users) |
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
| `tracerProvider` | `BasicTracerProvider` | `undefined` | Caller-owned private provider. Neatlogs adds its processors + flushes it, but never registers it globally or shuts it down |
| `registerShutdownHandlers` | `boolean` | `true` when Neatlogs owns the provider, else `false` | Register `beforeExit`/`SIGTERM`/`SIGINT` flush + shutdown handlers |

---

## OTel Isolation

Neatlogs runs on a **private `TracerProvider` and a private active-context store** — it never registers globally, and never adopts or shuts down a foreign global provider. A co-tenant tracer's active span (Datadog, Braintrust, another OTel SDK) can't become a Neatlogs parent, and vice-versa; `trace()`, auto-roots, `log()`, and `isRootSpan()` all resolve the active span from the private store.

- **`tracerProvider`** (init option): pass your own `BasicTracerProvider` — the SDK adds processors + flushes but never registers it globally or shuts it down.
- **`registerShutdownHandlers`** (init option): `beforeExit`/`SIGTERM`/`SIGINT` flush + shutdown; defaults `true` when Neatlogs owns the provider (so scripts drain spans), `false` when you pass `tracerProvider`.
- **`injectTraceContext(carrier)`**: caller-side W3C propagation. Returns `false` if no valid Neatlogs span is active.
- **`extractTraceContext(carrier, fn)`**: callee-side continuation. Runs `fn` under the inbound remote parent in Neatlogs' private context and returns its sync value or Promise. Invalid/missing headers are a fail-open passthrough.

```typescript
import { extractTraceContext, injectTraceContext, trace } from 'neatlogs';
const headers: Record<string, string> = {};
if (injectTraceContext(headers)) await fetch(url, { headers });

await extractTraceContext(request.headers, () =>
  trace({ name: 'remote_work' }, async () => { /* joins caller's trace */ }),
);
```

---

## Trace Output

`setTraceOutput(value)` stamps `neatlogs.trace.output` on the active trace's ROOT span, so the dashboard shows a meaningful output instead of a raw status object (e.g. an agent that suspends awaiting input). No-op outside a trace; never throws.

```typescript
import { trace, setTraceOutput } from 'neatlogs';
await trace({ name: 'turn', sessionId }, async () => {
  const plan = await proposePlan();
  setTraceOutput(plan.title); // show the plan, not the raw status object
});
```

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

Lineage uses `parentSessionId`; application-defined fields use one arbitrary `sessionCustomFields` object:

```typescript
await identify({
  sessionId: 'child_123',
  parentSessionId: 'parent_456',
  sessionCustomFields: { feature_name: 'chat', entry_point: 'slack', tenant: 'acme' },
}, runTurn);
```

Never hardcode a custom key as a new SDK option. Custom fields are encoded under `neatlogs.session.custom_fields`.

For retrieval spans, always emit the canonical `neatlogs.retriever.*`
namespace. `neatlogs.retrieval.*` is an ingestion-only legacy alias.

> **Browser SDK** (`neatlogs/browser`) uses the same field names — `endUserId`, `endUserMetadata`, `sessionId` — as client-constructor defaults or per-call on `trace()` / `trackAI()`.

---

## Supported Instrumentations

**There is no `instrumentations: [...]` path in the TypeScript SDK.** Each library gets an explicit helper you attach to the object yourself. This is the ONLY supported mechanism.

| Library | Helper | Import from |
|---|---|---|
| `openai` | `wrapOpenAI(client)` | `neatlogs` or `neatlogs/openai` |
| `@anthropic-ai/sdk` | `wrapAnthropic(client)` | `neatlogs` or `neatlogs/anthropic` |
| Azure OpenAI | `wrapAzureOpenAI(client)` | `neatlogs/azure-openai` |
| `@aws-sdk/client-bedrock-runtime` | `wrapBedrock(client)` | `neatlogs/bedrock` |
| `@google/genai` (Gemini / AI Studio, `provider=google`) | `wrapGoogleGenAI(client)`, `wrapGoogleGenAIChat(chat)` | `neatlogs/google-genai` |
| `@google/genai` in Vertex mode (`provider=vertex_ai`) | `wrapVertexAI(client)`, `wrapVertexAIChat(chat)` | `neatlogs/vertex-ai` |
| OpenRouter | `wrapOpenRouterAgent(client)`, `wrapCallModel(fn)` | `neatlogs/openrouter-agent` |
| Vercel AI SDK (`ai`) | `wrapAISDK(ai)` | `neatlogs/ai` |
| Mastra | `wrapMastra(entity)`, `wrapMastraRerank(fn)` | `neatlogs/mastra` |
| `@anthropic-ai/claude-agent-sdk` | `wrapClaudeAgentSDK(sdk)` | `neatlogs/claude-agent-sdk` |
| `@langchain/core` (covers LangGraph) | `langchainHandler()` → `config.callbacks` | `neatlogs` or `neatlogs/langchain` |
| OpenAI Agents SDK | `openaiAgentsProcessor()` → `addTraceProcessor()` | `neatlogs` |
| Strands / Pi agents | `strandsHooks(agent)` / `piAgentHooks(agent)` | `neatlogs` |
| OpenCode | `NeatlogsOpencodePlugin` | `neatlogs/opencode` |

The direct provider wrappers (`wrapOpenAI`, `wrapAnthropic`, `wrapAzureOpenAI`, `wrapBedrock`, `wrapGoogleGenAI`, `wrapVertexAI`, `wrapOpenRouterAgent`) also **auto-open a `WORKFLOW` root** when a call would otherwise be parentless, so a lone wrapped call renders on its own. Framework helpers root themselves.

### Why the instrumentations key throws

`init()` validates the list against the registry and rejects any key that loads an auto-instrumentor, because OpenInference/OTel-contrib instrumentors create *and* activate spans on the **global** OTel context — a private provider can't isolate that in either direction. The error names the replacement:

```
The "openai" auto-instrumentation uses the global OpenTelemetry context and cannot
guarantee isolation from other tracing SDKs (Datadog, etc.).

Use wrapOpenAI() from 'neatlogs/openai' for isolated tracing. Neatlogs does not
support shared global-context instrumentation.
```

Keys that load nothing (`crewai`, `litellm`, `cohere`, `groq`, `llamaindex`, and the vector-DB keys) are accepted but are **no-ops** — they patch nothing. Don't pass them either; they achieve nothing.

> This is the opposite of the **Python** SDK, where `instrumentations=[...]` is the primary path. Do not port a Python snippet's `instrumentations` list into TypeScript.

> **HTTP auto-instrumentation** (fetch/undici) is always enabled by `init()` for trace context propagation — nothing to configure.

---

## Reference Docs

For deep dives, see the companion reference files:

- **Custom instrumentation** with `span()`, `Span()`, and `trace()` → [`references/decorators-and-traces.md`](references/decorators-and-traces.md)
- **Raw HTTP LLM calls** (fetch/undici/axios — wrappers are BLIND, need manual spans; streaming lifecycle + per-provider field paths) → [`references/raw-http-llm.md`](references/raw-http-llm.md)
- **Framework-specific** integration patterns → [`references/framework-integrations.md`](references/framework-integrations.md)
- **Troubleshooting** and common mistakes → [`references/troubleshooting.md`](references/troubleshooting.md)
- **Multiple independent workflows in one codebase** (a copilot + a summarizer + a background job, each a distinct dashboard workflow) → use the `neatlogs-multi-workflow` skill. `workflowName` on `init()` is process-wide/single-shot; give each feature its own `WORKFLOW` root via `trace({ name, kind: 'WORKFLOW', attributes: { 'neatlogs.workflow.name': ... } }, …)`.

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
