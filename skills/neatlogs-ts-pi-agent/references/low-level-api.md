# Low-level Pi API

## Contents

- [Shared setup](#shared-setup)
- [EventStream loops](#eventstream-form)
- [Sink loops](#sink-form)
- [Standalone stream functions](#standalone-stream-function)

`piAgentHooks()` is for `Agent` and `AgentHarness`. Use
`tracePiAgentEvents()` for functional loops and `tracePiStream()` only for a
standalone model stream outside an agent loop.

| Maintained Pi entry point | Shape | Neatlogs helper |
|---|---|---|
| `agentLoop` / `agentLoopContinue` | returns `EventStream` | call `tracePiAgentEvents()` while iterating |
| `runAgentLoop` / `runAgentLoopContinue` | takes an event sink | call `tracePiAgentEvents()` from the sink |
| standalone `StreamFn` | `EventStream` or `Promise<EventStream>` | wrap it with `tracePiStream()` |

## Shared setup

```typescript
import {
  agentLoop,
  agentLoopContinue,
  runAgentLoop,
  runAgentLoopContinue,
  type AgentMessage,
} from "@earendil-works/pi-agent-core";
import { tracePiAgentEvents, tracePiStream } from "neatlogs/pi-agent";

const streamFn = models.streamSimple.bind(models);
const context = {
  systemPrompt: "Be concise.",
  messages: [] as AgentMessage[],
  tools,
};
const config = {
  model,
  convertToLlm: (messages: AgentMessage[]) => messages as any,
  getApiKey: () => process.env.OPENAI_API_KEY,
  getSteeringMessages: async () => [],
  getFollowUpMessages: async () => [],
};
```

## EventStream form

```typescript
const listener = tracePiAgentEvents(() => context.messages);
const stream = agentLoop(prompts, context, config, undefined, streamFn);
for await (const event of stream) listener(event);
context.messages.push(...(await stream.result()));

context.messages.push(nextUserMessage);
const continuationListener = tracePiAgentEvents(() => context.messages);
const continuation = agentLoopContinue(context, config, undefined, streamFn);
for await (const event of continuation) continuationListener(event);
await continuation.result();
```

Iteration is required: calling `.result()` alone does not deliver events to the
listener. Start iterating promptly so buffered events do not collapse observed timing.

The prompt-taking loop uses a copy of `context.messages`; append its returned messages
before continuing. The continuation shares the existing messages array.

## Sink form

```typescript
const listener = tracePiAgentEvents(() => context.messages);
const messages = await runAgentLoop(
  prompts,
  context,
  config,
  (event) => listener(event),
  undefined,
  streamFn,
);
context.messages.push(...messages);

context.messages.push(nextUserMessage);
const nextListener = tracePiAgentEvents(() => context.messages);
await runAgentLoopContinue(
  context,
  config,
  (event) => nextListener(event),
  undefined,
  streamFn,
);
```

Create a fresh listener for overlapping runs. Pass the transcript accessor for
continuations so their input can be recovered even though no new user event is emitted.

## Standalone stream function

```typescript
const tracedStream = tracePiStream(
  async (...args: Parameters<typeof streamFn>) => streamFn(...args),
);
const stream = await tracedStream(model, modelContext);
for await (const event of stream) consume(event);
const result = await stream.result();
```

The wrapper preserves synchronous and asynchronous `StreamFn` return shapes, observes
the caller's iteration without consuming it, records TTFT/streaming/output/usage/cost,
and closes spans on synchronous throws or promise rejection. Called outside an active
trace, it creates `WORKFLOW pi_agent.stream → LLM`; inside a trace it only adds the LLM.

Never pass a `tracePiStream()`-wrapped function into an Agent or functional loop—the
loop event listener already traces that model call and the combination would duplicate it.
