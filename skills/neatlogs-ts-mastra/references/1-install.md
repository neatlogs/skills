# Step 1: Install neatlogs + check Mastra version

## 1. Install neatlogs

1. Call `detect_package_manager` to get the install command (npm/pnpm/yarn/bun).
2. Install the LATEST `neatlogs` — always pull the newest published version, do not pin an older one:
   - npm: `npm install neatlogs@latest`
   - pnpm: `pnpm add neatlogs@latest`
   - yarn: `yarn add neatlogs@latest`
   - bun: `bun add neatlogs@latest`
3. Requires Node.js >= 18.

`wrapMastra` is self-contained — it does NOT require `@mastra/observability` or `@neatlogs/instrumentation-mastra`. It wraps Mastra's own methods directly.

## 2. Check Mastra version (informational)

```bash
cat package.json | grep '@mastra/core'
npm ls @mastra/core 2>/dev/null || cat node_modules/@mastra/core/package.json | grep '"version"'
```

| `@mastra/core` | Notes |
|---|---|
| `>= 1.0.0` | Fully supported. Tools use `execute: async (inputData, context) => ...` (input on the first arg). |
| `< 1.0.0` (e.g. `^0.4.0`) | `wrapMastra` still attaches AGENT/LLM/TOOL/WORKFLOW spans via method-wrapping, but the agent/tool/model APIs differ (legacy `model: { provider, name }`, `({ context })` tool signature). Recommend upgrading to `>= 1.0.0` for the validated behavior. |

Surface the version in your status output (e.g. `[STATUS] @mastra/core 1.37.1`).

## 3. If the project uses RAG rerank

`rerank()` lives in the separate `@mastra/rag` package. If the project calls it and you want RERANKER spans, ensure `@mastra/rag` is installed (it usually already is in a RAG project) and use `wrapMastraRerank()` (Step 2).

## Verification

- `neatlogs` appears in `package.json` dependencies.
- Mastra version noted.
