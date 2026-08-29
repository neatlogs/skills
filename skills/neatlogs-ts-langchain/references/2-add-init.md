# Step 2: Add init() and create the handler

Call `await init()` once at startup, then create the callback handler. LangChain imports can stay as plain static `import` statements — the handler binds to Neatlogs' private provider on each call, so there is no import-order rule.

```typescript
import "dotenv/config";
import { init, langchainHandler } from "neatlogs";
import { ChatOpenAI } from "@langchain/openai";

await init({
  apiKey: process.env.NEATLOGS_API_KEY ?? "",
  workflowName: "langchain-app",
});

const handler = langchainHandler();
const llm = new ChatOpenAI({ model: "gpt-4o" });
```


## Do NOT pass instrumentations — it throws

Do not add an `instrumentations` property to `init()`. It is unsupported and
throws. Use the working handler example above; public Skill documentation must
not emit a copyable unsupported initialization snippet, even as a negative example.

## Verify
1. `await init(...)` runs once at startup, before the first traced call.
2. `langchainHandler()` created ONCE, reused across calls.
3. No `instrumentations` key in `init()` at all.
