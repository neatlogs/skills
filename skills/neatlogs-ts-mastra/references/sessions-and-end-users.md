# Sessions & End-Users — NeatLogs TypeScript SDK (Mastra)

## Why

A Mastra agent usually serves many different customers, and each customer holds a
multi-turn conversation. To make traces useful for **customer analytics** — "show
me everything user `u_456` did", "replay this whole conversation", "which plan tier
is burning the most tokens" — you attach two identifiers to each turn:

- **session** — groups the turns of one conversation.
- **end-user** — the customer the agent is serving (NOT the SDK operator).

> The operator (your own app/service account) is `userId` on `init()`. The **end-user**
> is a customer of yours and is set per-turn, never on `init()`.

## The model

- `init()` has **no** `sessionId`, `autoSession`, or `endUser` params — the only identity
  it takes is `userId` (the operator).
- One `agent.generate(...)` call = **one trace**.
- A **session** groups the turns of a conversation — reuse the **same `sessionId`** across
  every `generate()` in that conversation.
- The **end-user** is set per session (same `endUserId` on every turn of the conversation).
- Identity is **root-only**: you set it once on the wrapper's auto-root and the backend
  rolls it up across the whole trace tree (AGENT → LLM → TOOL).

Because `wrapMastra` owns the root span, you don't build a manual root. Wrapper-only
code uses **`identify()`** — the Mastra agent's root inherits the session + end-user:

```typescript
import { identify } from 'neatlogs';

await identify(
  { sessionId: 'conv_123', endUserId: 'u_456', endUserMetadata: { plan: 'pro' } },
  async () => {
    await agent.generate(message);
  },
);
```

## Multi-turn example

Wrap each turn's `agent.generate(...)` in `identify()`, reusing the SAME `sessionId`
and `endUserId` for every turn of the same conversation:

```typescript
import { init, flush, shutdown, identify } from 'neatlogs';
import { wrapMastra } from 'neatlogs/mastra';

await init({ apiKey: process.env.NEATLOGS_API_KEY ?? '', workflowName: 'support-app' });

const { supportAgent } = await import('./agents/index.js');
const agent = wrapMastra(supportAgent);

// One conversation = one sessionId, one end-user, many turns.
const sessionId = 'conv_123';
const endUserId = 'u_456';
const endUserMetadata = { plan: 'pro' };

async function turn(message: string) {
  return identify({ sessionId, endUserId, endUserMetadata }, async () => {
    const res = await agent.generate(message); // one trace, root inherits identity
    return res.text;
  });
}

await turn('How do I reset my API key?');       // trace 1
await turn('And can I have more than one key?'); // trace 2, same session + end-user
await turn('Thanks — cancel the old one.');      // trace 3, same session + end-user

await flush();
await shutdown();
```

A different customer or a new conversation just uses a different `sessionId` /
`endUserId` in its own `identify()` block.

## Dashboard

The `sessionId` and `endUserId` become filters in the NeatLogs dashboard — filter the
trace list by end-user to see one customer's history, or by session to view every turn
of a single conversation together.
