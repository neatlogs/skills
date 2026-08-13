# Sessions & End-Users — NeatLogs TypeScript SDK (Pi Agent)

Lineage uses `parentSessionId`. Application-specific session data belongs in the
arbitrary `sessionCustomFields` object and is stored as
`neatlogs.session.custom_fields`; never add a fixed SDK option for an individual
custom key:

```typescript
await identify({
  sessionId: 'child_123',
  parentSessionId: 'parent_456',
  sessionCustomFields: { feature_name: 'chat', entry_point: 'slack', tenant: 'acme' },
  endUserId: 'u_456',
}, runTurn);
```


## Contents

- [Identity model](#the-model)
- [Multi-turn example](#multi-turn-example)
- [Functional loops](#low-level-api)
- [Dashboard behavior](#dashboard)

## Why

A Pi agent usually serves many different customers, and each customer holds a
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
- One `agent.prompt(...)` call = **one trace**. This is why a conversation shows up as
  several traces: you group them with a session, you do not merge them into one trace.
- A **session** groups the turns of a conversation — reuse the **same `sessionId`** across
  every `prompt()` in that conversation, even on the same `Agent` instance.
- The **end-user** is set per session (same `endUserId` on every turn of the conversation).
- Identity is **root-only**: you set it once on the wrapper's auto-root and the backend
  rolls it up across the whole trace tree (AGENT → CHAIN → LLM/TOOL).

Because `piAgentHooks` owns the root span, you don't build a manual root. Wrapper-only
code uses **`identify()`** — the Pi agent's AGENT root inherits the session + end-user:

```typescript
import { identify } from 'neatlogs';

await identify(
  { sessionId: 'conv_123', endUserId: 'u_456', endUserMetadata: { plan: 'pro' } },
  async () => {
    await agent.prompt(message);
  },
);
```

`identify()` must wrap the `prompt()` call itself — that is when `agent_start` fires and
the root span is created.

## Multi-turn example

```typescript
import { init, flush, shutdown, identify } from 'neatlogs';
import { piAgentHooks } from 'neatlogs/pi-agent';
import { Agent } from '@earendil-works/pi-agent-core';
import { Type, createModels } from '@earendil-works/pi-ai';
import { openaiProvider } from '@earendil-works/pi-ai/providers/openai';

await init({ apiKey: process.env.NEATLOGS_API_KEY ?? '', workflowName: 'support-app' });

const models = createModels();
models.setProvider(openaiProvider());
const model = models.getModel('openai', 'gpt-4o-mini');
if (!model) throw new Error('Model is not in the Pi catalog');

const agent = piAgentHooks(
  new Agent({
    initialState: {
      systemPrompt: 'You are a terse support agent.',
      model,
      tools: [lookupTool],
      messages: [],
    },
  }),
);

// One conversation = one sessionId, one end-user, many turns.
const sessionId = 'conv_123';
const endUserId = 'u_456';
const endUserMetadata = { plan: 'pro' };

async function turn(message: string) {
  await identify({ sessionId, endUserId, endUserMetadata }, async () => {
    await agent.prompt(message);   // one trace, root inherits identity
  });
  await agent.waitForIdle();
  return agent.state.messages.at(-1);
}

await turn('How do I reset my API key?');        // trace 1
await turn('And can I have more than one key?'); // trace 2, same session + end-user
await turn('Thanks — cancel the old one.');      // trace 3, same session + end-user

await flush();
await shutdown();
```

A different customer or a new conversation just uses a different `sessionId` /
`endUserId` in its own `identify()` block. A `reset()` on the agent usually means a new
conversation — give it a new `sessionId`.

## Low-level API

The same rule applies to `runAgentLoop` / `agentLoop`: wrap the call (and its iteration)
in `identify()`, since that is when the loop emits `agent_start`.

```typescript
await identify({ sessionId, endUserId }, async () => {
  const traceEvent = tracePiAgentEvents(() => context.messages);
  await runAgentLoop(prompts, context, config, async (e) => traceEvent(e));
});
```

## Dashboard

The `sessionId` and `endUserId` become filters in the NeatLogs dashboard — filter the
trace list by end-user to see one customer's history, or by session to view every turn
of a single conversation together.
