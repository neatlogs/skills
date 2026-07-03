# Sessions & End-Users

## Why

Group an end-user's turns into one conversation and attach who they are, so you
can slice traces by customer in the dashboard — answer "what did user u_456 see
across this whole chat?" and build per-customer analytics, not just per-request
noise.

## The model

- **One turn = one trace.** Each `.invoke(...)` produces its own trace
  (LangChain self-roots — `instrumentations: ['langchain']` traces it).
- **A session groups turns.** Reuse the SAME `sessionId` across every turn of a
  conversation and the backend rolls them up into one session.
- **End-user is per session.** `endUserId` (+ optional `endUserMetadata`)
  identifies the customer's end-user for that session.
- **Root-only.** Identity is set once at the trace root — here, LangChain's own
  root and every span under it inherit it. You do NOT set it per span.
- `init()` takes NO `sessionId` / `autoSession` / `endUser` params. Its `userId`
  is the SDK operator (you), not the customer's end-user.

## Wrapper-only: `identify()`

LangChain self-instruments and opens its own trace root, so there is no manual
`span({ kind:'WORKFLOW' })` to hang identity on. Use the wrapper-only
`identify()` — LangChain's auto-root (and its children) inherit whatever is set
in the enclosing `identify()` scope.

```typescript
import { init, identify } from 'neatlogs';

// instrumentations: ['langchain'] must run BEFORE importing @langchain/*
await init({
  apiKey: process.env.NEATLOGS_API_KEY,
  workflowName: 'support-bot',
  instrumentations: ['langchain'],
});

const { ChatOpenAI } = await import('@langchain/openai');
const llm = new ChatOpenAI({ model: 'gpt-4o' });

// One conversation = one sessionId, reused across every turn.
const sessionId = 'conv_123';
const identity = { sessionId, endUserId: 'u_456', endUserMetadata: { plan: 'pro' } };

// Turn 1
await identify(identity, async () => {
  await llm.invoke('How do I reset my password?');
});

// Turn 2 — SAME sessionId + endUserId groups it into the same session.
await identify(identity, async () => {
  await llm.invoke('And how do I enable 2FA?');
});
```

Each `invoke` is its own trace; both carry `sessionId: conv_123` +
`endUserId: u_456`, so the backend groups them into one session for that user.

## Dashboard

Filter traces by `sessionId` to see a full conversation, or by `endUserId` to
see everything one customer's end-user did.
