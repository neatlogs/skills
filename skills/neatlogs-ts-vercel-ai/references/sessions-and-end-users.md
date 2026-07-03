# Sessions & End-Users — NeatLogs Vercel AI SDK

Attach **session** and **end-user** identity to your `wrapAISDK` calls so the dashboard can slice
usage, cost, and errors **per customer end-user** and **per segment**, stitch a customer's turns into
a **multi-turn timeline**, and drive **per-customer replay**. The identity here is your *product's*
end-user — NOT the SDK operator (that's `userId` on `init()`).

## The model

- **One `generateText`/`streamText` call = one trace.** The wrapper opens the root span for you.
- **A session groups turns**: reuse the **same `sessionId`** across every call in a conversation.
- **End-user is per session**: pass the same `endUserId` (and optional `endUserMetadata`) on each turn.
- **Root-only**: identity is set on the trace root; the backend rolls it up across all child spans.
- `init()` has **no** `sessionId` / `autoSession` / `endUser` params — session/end-user are per-turn only.

## Wrapper-only: `identify()`

Because this skill instruments via `wrapAISDK(...)` (no manual root `span()`/`trace()`), set identity
by wrapping each turn in `identify()`. The wrapped call's auto-root inherits it:

```typescript
import { identify } from "neatlogs";

await identify(
  { sessionId: "conv_123", endUserId: "u_456", endUserMetadata: { plan: "pro" } },
  async () => {
    await generateText({ model, prompt: message });
  },
);
```

## Multi-turn chatbot example

Same `sessionId` + `endUserId` on every turn → one session grouped under one end-user:

```typescript
import "dotenv/config";
import { init, identify } from "neatlogs";
import { wrapAISDK } from "neatlogs/ai";

await init({ apiKey: process.env.NEATLOGS_API_KEY ?? "", workflowName: "support-bot" });

const ai = await import("ai");
const { openai } = await import("@ai-sdk/openai");
const { generateText } = wrapAISDK(ai);

// One live conversation with a specific customer.
const sessionId = "conv_123";       // stable for the whole conversation
const endUserId = "u_456";          // the customer talking to the bot
const endUserMetadata = { plan: "pro", org: "acme" };

async function handleTurn(message: string) {
  return identify({ sessionId, endUserId, endUserMetadata }, async () => {
    const { text } = await generateText({
      model: openai("gpt-4o-mini"),
      prompt: message,
    });
    return text;
  });
}

// Each turn is its own trace; all three land in the same session, same end-user.
await handleTurn("How do I reset my password?");
await handleTurn("It says my token expired.");
await handleTurn("Thanks — that worked!");
```

`streamText` works the same way — wrap the call in `identify()` and consume the stream inside the callback.

## Dashboard

Filter traces by **session** to replay a full conversation, or by **end-user** (and `endUserMetadata`
fields like `plan`) to see usage, cost, and errors for one customer or segment.
