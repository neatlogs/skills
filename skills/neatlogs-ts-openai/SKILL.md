---
name: neatlogs-ts-openai
description: Use when adding neatlogs observability to a TypeScript/Node.js project that calls LLM provider SDKs directly (OpenAI, Anthropic, Google GenAI, Bedrock) and uses no agent framework.
compatibility: Neatlogs Wizard Agent
metadata:
  author: neatlogs
  language: typescript
  framework: openai
---

# Neatlogs TypeScript Setup — Direct LLM SDK (OpenAI / Anthropic / Google / Bedrock)

This project calls an LLM provider SDK directly (no agent framework). Neatlogs instruments the provider with an **explicit `wrap*` helper applied to the client instance**; you add `span()` wrappers on orchestration functions and `trace()` + prompt templates around LLM calls.

> **`init({ instrumentations: [...] })` throws.** Every provider key is rejected — the underlying instrumentors drive the **global** OpenTelemetry context, which Neatlogs' private provider cannot isolate from a co-tenant tracer (Datadog, etc.). The thrown error names the helper to use instead. Older guidance offered the key as a zero-touch path — that is gone.

## Core mechanism

1. `await init({ apiKey })` once at startup — with NO `instrumentations` key.
2. Wrap each provider client at its construction site: `const client = wrapOpenAI(new OpenAI())`.
3. `span({ kind: 'WORKFLOW' }, fn)` wraps the user-facing entry; `trace({ kind:'LLM', promptTemplate, userPromptTemplate }, fn)` wraps each LLM call for prompt management.

## Provider → helper

| SDK | Helper | Import from |
|---|---|---|
| OpenAI | `wrapOpenAI(new OpenAI())` | `neatlogs/openai` |
| Azure OpenAI | `wrapAzureOpenAI(client)` | `neatlogs/azure-openai` |
| Anthropic | `wrapAnthropic(new Anthropic())` | `neatlogs/anthropic` |
| Google GenAI (Gemini / AI Studio) | `wrapGoogleGenAI(new GoogleGenAI({ apiKey }))` | `neatlogs/google-genai` |
| Google GenAI (Vertex mode) | `wrapVertexAI(client)` | `neatlogs/vertex-ai` |
| AWS Bedrock | `wrapBedrock(new BedrockRuntimeClient({}))` | `neatlogs/bedrock` |

All of these are also re-exported from the root `neatlogs` entry. Wrap once, at construction, and use the returned client everywhere — then call it exactly as normal (`gc.models.generateContent(...)`, `client.chat.completions.create(...)`). Because the helpers patch the **instance** and not the module, there is **no import-order rule**: plain static imports are correct and dynamic `import()` buys nothing.

A provider with no helper (Cohere, Groq, Mistral, Ollama, Together, raw `fetch`) is **not** traced — instrument those calls with a manual `trace({ kind: 'LLM' })` span.

## Steps

1. **Install** → `references/1-install.md`
2. **Add init() + wrap the client** → `references/2-add-init.md`
3. **Set environment variables** → `references/3-set-env.md`
4. **Wrap orchestration with span() + LLM calls with trace()+templates** → `references/4-spans-and-traces.md`
5. **Lifecycle (flush/shutdown)** → `references/5-lifecycle.md`

## Rules (apply to ALL steps)

- `await init(...)` runs once at startup. Import order does NOT matter — the helpers patch the client instance, so static imports of the LLM SDK are fine and no dynamic `import()` is needed.
- NEVER pass `instrumentations: [...]` to `init()` — it **throws** for every provider key. Wrap the client instead.
- Every provider client the code constructs must be wrapped; an unwrapped client is silently untraced.
- All lifecycle calls are async: `await init/flush/shutdown`.
- The wrapper captures the raw LLM call (model/tokens/latency) and auto-opens a WORKFLOW root if the call would be parentless. You still add `trace()` + `PromptTemplate`/`UserPromptTemplate` for prompt-management visibility, and `span()` to group a multi-step feature under one named root.
- COMPILE templates and pass the compiled output to the actual call (`tpl.compile({...})` → the `messages`/`system` you send). A template declared but not compiled-and-used is decorative/broken.
- `{{variables}}` are for genuinely dynamic data (user input, context), NEVER for a whole authored prompt selected at runtime — make one template per variant instead.
- Never hardcode API keys — use `process.env`.

## Reference

- **Next.js setup (init via dynamic import in instrumentation.ts)** → `references/nextjs.md` — REQUIRED if the project is a Next.js app, else the server 500s with `Can't resolve 'crypto'` and emits no traces.
- Custom span()/trace() deep dive → `references/decorators-and-traces.md`
- Sessions & end-users (per-turn `identify()`) → `references/sessions-and-end-users.md`
- Prompt templates → `references/prompt-templates.md`
- Troubleshooting → `references/troubleshooting.md`
