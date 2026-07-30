# Step 2: init() + wrapAISDK

Two pieces: init first (registers the tracer), then wrap the `ai` module and use the wrapped functions.

```typescript
import "dotenv/config";
import * as ai from "ai";
import { openai } from "@ai-sdk/openai";
import { init } from "neatlogs";
import { wrapAISDK } from "neatlogs/ai";

await init({
  apiKey: process.env.NEATLOGS_API_KEY ?? "",
  workflowName: "ai-sdk-app",
  // NOTE: no instrumentations key — init() THROWS for 'ai_sdk'. The wrapper is the instrumentation.
});

// wrapAISDK takes the ai module namespace and returns wrapped functions.
// Plain static imports are correct — there is no import-order rule.
const { generateText, streamText, generateObject, streamObject, embed, embedMany, rerank } = wrapAISDK(ai);

// Use the WRAPPED functions exactly like the originals.
const { text } = await generateText({
  model: openai("gpt-4o-mini"),
  prompt: "What is the capital of France?",
});
```

## What each wrapped call produces
- A parent span: `WORKFLOW` for generateText/streamText/generateObject/streamObject; `CHAIN` for embed/embedMany/rerank.
- The AI SDK's native `ai.doGenerate`/`ai.doStream` child spans → `LLM`.
- Tool-call children → `TOOL`.
- Captures model, tokens, input/output. `generateText`/`generateObject` capture the awaited result; `streamText`/`streamObject` capture `output.value` + `gen_ai.finish_reason` from the AI SDK `onFinish` callback (any user `onFinish`/`onError` is preserved). `generateObject`/`streamObject` structured output maps to the LLM child's output.

## Converting existing call sites

If the code imports AI SDK functions directly, replace those with the wrapped versions:

```typescript
// ❌ BEFORE — direct import, NOT traced
import { generateText } from "ai";
const { text } = await generateText({ model, prompt });

// ✅ AFTER — wrapped, traced
import * as ai from "ai";
const { generateText } = wrapAISDK(ai);
const { text } = await generateText({ model, prompt });
```

## Lower-level alternative (single call, no module wrap)
```typescript
import { generateText } from "ai";
import { createAITelemetry } from "neatlogs/ai";
await generateText({ model, prompt, experimental_telemetry: createAITelemetry({ metadata: { userId } }) });
```

## Verify
1. `await init(...)` runs before `wrapAISDK`.
2. NO `instrumentations` key in init at all — `init()` throws for `'ai_sdk'`.
3. The AI SDK functions actually CALLED are the ones from `wrapAISDK(ai)`, not bare `import ... from 'ai'`.
