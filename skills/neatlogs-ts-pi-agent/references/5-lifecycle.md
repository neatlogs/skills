# Step 5: Lifecycle (flush / shutdown)

All lifecycle calls are async — `await` them.

## Finish active work first

Await the promise returned by `prompt()` (or the functional loop result). Use
`waitForIdle()` when work was started elsewhere or queue operations may still be active.

```typescript
await agent.prompt("…");
```

## Script / one-shot run (CLI, `tsx src/index.ts`)

```typescript
async function main() {
  await agent.prompt("What is the weather in Lisbon?");
}

main()
  .catch((err) => { console.error(err); process.exitCode = 1; })
  .finally(async () => {
    await flush();
    await shutdown();
  });
```

If the entry already has a `main().catch(...)`, add a `.finally()` with `await flush(); await shutdown();`. Do NOT leave them out — a script that exits without flushing loses the last batch of spans.

## Long-running server (Express/Fastify/etc.)

Call `init()` ONCE at startup. Do NOT flush/shutdown per request.

```typescript
process.on("SIGTERM", async () => {
  await flush();
  await shutdown();
  process.exit(0);
});
```

## Aborted runs

`agent.abort()` still produces a complete trace: the AGENT span is marked ERROR with `neatlogs.agent.stop_reason = aborted` and `neatlogs.error.message`, and any tool or LLM span still open is closed rather than leaked. Await the prompt promise before flushing:

```typescript
const p = agent.prompt("Long job…");
agent.abort();
await p.catch(() => {});
```

## Verify
- [ ] Every active run/queue operation is settled before `flush()`.
- [ ] Script: `await flush()` then `await shutdown()` after the work (e.g. in `main().finally(...)`).
- [ ] Server: init once at startup; flush/shutdown only on SIGTERM/SIGINT, never per-request.
