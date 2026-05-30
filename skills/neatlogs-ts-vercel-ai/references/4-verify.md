# Step 4: Verify — Wrapped Functions Used, No Double-Wrapping

## What to check

1. **All AI SDK call sites use the wrapped functions.** Grep for `generateText`, `streamText`, `generateObject`, `streamObject`, `embed`, `embedMany`, `rerank`. Each call must resolve to a function from `wrapAISDK(ai)`, not a bare `import { generateText } from 'ai'`.

```typescript
// ❌ WRONG — still calling the unwrapped import → no trace.
import { generateText } from "ai";
await generateText({ model, prompt });

// ✅ RIGHT — calling the wrapped function.
const { generateText } = wrapAISDK(await import("ai"));
await generateText({ model, prompt });
```

2. **No double-wrapping.** Do NOT put `span()`/`trace()` around a single wrapped call — the wrapper already opens the parent span. Wrapping again creates a redundant nesting.

```typescript
// ❌ WRONG — wrapped call already creates a WORKFLOW span; this double-wraps.
await span({ kind: "LLM" }, async () => generateText({ model, prompt }));

// ✅ RIGHT — just call the wrapped function.
await generateText({ model, prompt });
```

3. **Grouping is OK.** A single `span({ kind:"WORKFLOW" }, ...)` wrapping a function that makes SEVERAL wrapped AI-SDK calls is fine — it groups them under one trace root. Just don't wrap an individual call.

## Verify
- [ ] Every AI SDK call site uses a `wrapAISDK(ai)` function (no bare `ai` imports being called).
- [ ] No `span()`/`trace()` around an individual wrapped call.
- [ ] `init()` has no `instrumentations: ['ai_sdk']`.
