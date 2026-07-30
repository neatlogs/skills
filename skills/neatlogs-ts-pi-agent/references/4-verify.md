# Step 4: Verify — every Agent wrapped, correct entry point

## 1. Find every Pi entry point

```bash
rg 'new (Agent|AgentHarness)\(|agentLoop|runAgentLoop|stream(Simple|Proxy)' src
```

Every `Agent` or `AgentHarness` whose runs should be traced must pass through `piAgentHooks()`. Functional loop or standalone stream call sites use the low-level helpers instead.

## 2. Confirm the wrapped reference is the one used

```typescript
// ✅ the wrapped reference is called
const agent = piAgentHooks(new Agent({ initialState }));
await agent.prompt("…");

// ✅ also fine — piAgentHooks patches in place, so the original is traced too
const agent = new Agent({ initialState });
piAgentHooks(agent);
await agent.prompt("…");

// ❌ result discarded AND the un-subscribed instance used elsewhere
piAgentHooks(new Agent({ initialState }));
await someOtherAgent.prompt("…");   // not traced
```

Unlike module-patching wrappers, `piAgentHooks` subscribes to the instance, so both of the first two forms work. What does NOT work is forgetting an instance entirely.

## 3. Finish active work before flushing

Awaiting `prompt()` settles that run. If work was started without directly awaiting its
handle, or queues may still be active, use `waitForIdle()` before the process-level flush.

```typescript
await agent.prompt("…");
await agent.waitForIdle();   // useful when other queued work may still be active
await flush();
```

## 4. Do not double-instrument

- No `instrumentations: [...]` in `init()`.
- No `wrapOpenAI` / `wrapAnthropic` for models Pi calls through `pi-ai`; `piAgentHooks` already captures that call. Wrap a provider client only when the app also calls it directly outside Pi.
- No `span()`/`trace()` of kind AGENT around `agent.prompt()`. Nesting inside a `WORKFLOW` span is fine.
- Calling `piAgentHooks` twice on one instance is safe (no-op).

## 5. Run it and check the span tree

Run the app, then confirm in the neatlogs dashboard that one `prompt()` produced one trace shaped like:

```
AGENT  pi_agent.run                    ← input = first user message, output = final answer
 ├─ CHAIN pi_agent.turn.1              ← turn_index 1
 │   ├─ LLM  pi_agent.llm.<model>      ← duration ≈ provider latency, non-zero cost + tokens
 │   └─ TOOL pi_agent.tool.<name>      ← args in, result out
 └─ CHAIN pi_agent.turn.2
     └─ LLM  pi_agent.llm.<model>
```

Checklist:
- [ ] LLM span durations look like real calls (hundreds of ms), not ~0ms.
- [ ] LLM spans show token counts AND a non-zero cost.
- [ ] TOOL spans show input args and the result; a failing tool is marked ERROR.
- [ ] A multi-turn run (tool call → answer) shows more than one CHAIN span.
- [ ] The AGENT span has both input and output.
- [ ] If the run was aborted, the AGENT span is ERROR with `neatlogs.agent.stop_reason = aborted`.

## Common problems

| Symptom | Cause |
|---|---|
| No traces at all | `init()` never ran, ran after the prompt, or `flush()` was skipped |
| Some runs missing | an `Agent` instance was never passed to `piAgentHooks` |
| Last run's spans missing | active run/queue work was not awaited before `flush()`/`shutdown()` |
| No spans from a loop-based app | project uses `agentLoop`/`runAgentLoop`, which have no `subscribe()` → use `tracePiAgentEvents()` (`references/low-level-api.md`) |
| Duplicate LLM spans | a provider client was ALSO wrapped, or a custom `streamFn` was wrapped with `tracePiStream` while the agent loop already traces it |
