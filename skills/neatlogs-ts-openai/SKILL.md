---
name: neatlogs-ts-openai
description: Use when adding neatlogs observability to a TypeScript/Node.js project that calls LLM provider SDKs directly (OpenAI, Anthropic, Google GenAI, Bedrock) and uses no agent framework.
compatibility: Neatlogs Wizard Agent
metadata:
  author: neatlogs
  version: "2.0"
  language: typescript
  framework: openai
---

# Neatlogs TypeScript Setup — Direct LLM SDK (OpenAI / Anthropic / Google / Bedrock)

This project calls an LLM provider SDK directly (no agent framework). Neatlogs auto-instruments the provider via the `instrumentations` list; you add `span()` wrappers on orchestration functions and `trace()` + prompt templates around LLM calls.

## Core mechanism

1. `await init({ instrumentations: [<provider>] })` BEFORE importing the LLM SDK.
2. Dynamic-`import()` the LLM SDK AFTER init (so it's patched).
3. `span({ kind: 'WORKFLOW' }, fn)` wraps the user-facing entry; `trace({ kind:'LLM', promptTemplate, userPromptTemplate }, fn)` wraps each LLM call for prompt management.

## Provider → instrumentation key

| SDK | key | import |
|---|---|---|
| OpenAI | `openai` | `await import('openai')` |
| Anthropic | `anthropic` | `await import('@anthropic-ai/sdk')` |
| Google GenAI | `google_genai` | `await import('@google/genai')` |
| AWS Bedrock | `bedrock` | bedrock client SDK |

## Steps

1. **Install** → `references/1-install.md`
2. **Add init() (before LLM import)** → `references/2-add-init.md`
3. **Set environment variables** → `references/3-set-env.md`
4. **Wrap orchestration with span() + LLM calls with trace()+templates** → `references/4-spans-and-traces.md`
5. **Lifecycle (flush/shutdown)** → `references/5-lifecycle.md`

## Rules (apply to ALL steps)

- `await init(...)` MUST run BEFORE any `import` of the LLM SDK. Use dynamic `import()` for the SDK AFTER init.
- All lifecycle calls are async: `await init/flush/shutdown`.
- Auto-instrumentation captures the raw LLM call (model/tokens/latency). You still add `trace()` + `PromptTemplate`/`UserPromptTemplate` for prompt-management visibility, and `span()` to bind a WORKFLOW root.
- COMPILE templates and pass the compiled output to the actual call (`tpl.compile({...})` → the `messages`/`system` you send). A template declared but not compiled-and-used is decorative/broken.
- `{{variables}}` are for genuinely dynamic data (user input, context), NEVER for a whole authored prompt selected at runtime — make one template per variant instead.
- Never hardcode API keys — use `process.env`.

## Reference

- **Next.js setup (init via dynamic import in instrumentation.ts)** → `references/nextjs.md` — REQUIRED if the project is a Next.js app, else the server 500s with `Can't resolve 'crypto'` and emits no traces.
- Custom span()/trace() deep dive → `references/decorators-and-traces.md`
- Prompt templates → `references/prompt-templates.md`
- Troubleshooting → `references/troubleshooting.md`
