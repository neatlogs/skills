# Step 4: Verify — Wrapped Functions Used, No Double-Wrapping

## What to check

1. **All AI SDK call sites use the wrapped functions.** Grep for `generateText`, `streamText`, `generateObject`, `streamObject`, `embed`, `embedMany`, `rerank`. Each call must resolve to a function from `wrapAISDK(ai)`, not a bare `import { generateText } from 'ai'`.

```typescript
// ❌ WRONG — still calling the unwrapped import → no trace.
import { generateText } from "ai";
await generateText({ model, prompt });

// ✅ RIGHT — calling the wrapped function.
import * as ai from "ai";
const { generateText } = wrapAISDK(ai);
await generateText({ model, prompt });
```

2. **No double-wrapping.** Do NOT put `span()`/`trace()` around a single wrapped call — the wrapper already opens the parent span. Wrapping again creates a redundant nesting.

```typescript
// ❌ WRONG — wrapped call already creates a WORKFLOW span; this double-wraps.
await span({ kind: "LLM" }, async () => generateText({ model, prompt }));

// ✅ RIGHT — just call the wrapped function.
await generateText({ model, prompt });
```

3. **App-owned orchestration is valid.** Add one `WORKFLOW` only when the user-facing request/job performs meaningful pre/post work or coordinates multiple wrapped AI-SDK calls. The wrapped calls remain canonical children; never add a span around an individual call.

## Verify
- [ ] Every AI SDK call site uses a `wrapAISDK(ai)` function (no bare `ai` imports being called).
- [ ] No `span()`/`trace()` around an individual wrapped call.
- [ ] `init()` has no `instrumentations` key at all (it throws for `'ai_sdk'`).
