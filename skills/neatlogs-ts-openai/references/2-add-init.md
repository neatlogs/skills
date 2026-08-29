# Step 2: Add init() and wrap the client

Call `await init()` once at startup, then wrap each provider client at its construction site. LLM SDK imports stay plain static `import` statements — the helper patches the client **instance**, so there is no import-order rule.

```typescript
import "dotenv/config";
import { init, wrapOpenAI } from "neatlogs";
import { OpenAI } from "openai";

await init({
  apiKey: process.env.NEATLOGS_API_KEY ?? "",
  workflowName: "my-app",
});

const client = wrapOpenAI(new OpenAI());   // use THIS client everywhere
```

Pick the helper for the detected provider (all re-exported from `neatlogs`, or importable from their subpath):

| SDK | Helper | Import from |
|---|---|---|
| OpenAI | `wrapOpenAI(new OpenAI())` | `neatlogs/openai` |
| Azure OpenAI | `wrapAzureOpenAI(client)` | `neatlogs/azure-openai` |
| Anthropic | `wrapAnthropic(new Anthropic())` | `neatlogs/anthropic` |
| Google GenAI (Gemini) | `wrapGoogleGenAI(new GoogleGenAI({ apiKey }))` | `neatlogs/google-genai` |
| Google GenAI (Vertex) | `wrapVertexAI(client)` | `neatlogs/vertex-ai` |
| AWS Bedrock | `wrapBedrock(new BedrockRuntimeClient({}))` | `neatlogs/bedrock` |

## Do NOT pass instrumentations — it throws

Do not add an `instrumentations` property to `init()`. It is unsupported and
throws. Use the working wrapper example above; public Skill documentation must
not emit a copyable unsupported initialization snippet, even as a negative example.

Dynamic `await import("openai")` is also pointless here — it was only ever needed to beat a module-patching instrumentor, and there isn't one. Use a static import.

## Top-level await
If the project isn't ESM/top-level-await friendly, run `init()` inside an async bootstrap that executes before the first traced call.

## Verify
1. `await init(...)` runs once at startup, with NO `instrumentations` key.
2. Every provider client the code constructs is passed through its `wrap*` helper, and the WRAPPED value is what the rest of the code calls.
3. LLM SDK imports are plain static imports.
