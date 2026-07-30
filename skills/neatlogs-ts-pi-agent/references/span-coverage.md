# Pi Agent — full span coverage

Every row below was verified against real provider calls (no mocks). Use this to answer "is X traced?" without re-running an experiment.

## Span tree

```
AGENT  pi_agent.run                    agent_start  → agent_end
 └─ CHAIN pi_agent.turn.N              turn_start   → turn_end
     ├─ LLM  pi_agent.llm.<model>      message_start → message_end   (assistant messages only)
     └─ TOOL pi_agent.tool.<name>      tool_execution_start → tool_execution_end
```

The AGENT span is opened as the active span, so it parents everything below it — and itself parents to any `span()`/`trace()` block active when `prompt()` is called.

## Pi surface → what happens

| Pi API | Traced | Result |
|---|---|---|
| `agent.prompt(text)` / `prompt(msg[])` | ✅ | one trace per call |
| `agent.continue()` | ✅ | one trace; input recovered from the transcript (no new user message is emitted) |
| `agent.steer(msg)` | ✅ | injected message becomes another CHAIN turn in the SAME trace |
| `agent.followUp(msg)` | ✅ | queued message becomes another CHAIN turn in the same trace |
| `agent.abort()` | ✅ | AGENT span ERROR, `stop_reason = aborted`, `neatlogs.error.message`; open LLM/TOOL spans are closed, not leaked |
| `agent.reset()` then reuse | ✅ | next `prompt()` starts a fresh trace, turn numbering restarts |
| `agent.waitForIdle()` | n/a | synchronization helper for work started elsewhere or queued work |
| `AgentHarness.prompt` / `continue` / queues / tools | ✅ | same Agent event tree |
| `AgentHarness.compact()` | ✅ | `WORKFLOW → CHAIN → LLM`, including summary I/O and usage |
| `AgentHarness.navigateTree(..., { summarize: true })` | ✅ | `WORKFLOW → CHAIN → LLM` for the generated branch summary |
| `AgentHarness.navigateTree(..., { summarize: false })` | ✅ | CHAIN-only operation; no fake LLM span |
| harness model/tool/resource getters and setters | n/a | state only; effects appear on later calls |
| `Session` / `SessionRepo` persistence, labels, bookmarks, branches, stats | n/a | storage/state operations; no model or tool work |
| `agent.clearSteeringQueue()` / `clearFollowUpQueue()` / `clearAllQueues()` / `hasQueuedMessages()` / `state` / `signal` | n/a | no model or tool work → nothing to trace |
| streaming (Pi's default) | ✅ | `is_streaming = true`, `metrics.ttft_ms` from the first content delta |
| non-streaming / no deltas | ✅ | `is_streaming = false`, no TTFT |
| tools in `parallel` mode (Pi's default) | ✅ | one TOOL span per call, keyed by `toolCallId` — correct even when they overlap |
| tools in `sequential` mode | ✅ | one TOOL span per call |
| a tool that throws | ✅ | TOOL span ERROR + `neatlogs.tool.is_error`, message from the tool's own error content |
| a tool that calls `onUpdate` (partial results) | ✅ | `neatlogs.tool.is_streaming = true`; final result still lands on `output` |
| two agents running concurrently | ✅ | per-agent state is isolated; no cross-talk |
| double-wrapping one agent | ✅ | second call is a no-op |
| thinking / reasoning blocks | ✅ | counted for TTFT; omitted from the main output text |
| `agentLoop` / `agentLoopContinue` / `runAgentLoop` / `runAgentLoopContinue` | ✅ | via `tracePiAgentEvents()` → same tree (see `low-level-api.md`). The prompt-taking forms run on a COPY of your context, so append their returned messages back or a later continuation's input can't be recovered |
| standalone sync or async `StreamFn` | ✅ | via `tracePiStream()` → streaming/TTFT, I/O, usage, cost, and an LLM under a `pi_agent.stream` WORKFLOW root |

## Attributes

### AGENT — `pi_agent.run`
| Attribute | Notes |
|---|---|
| `neatlogs.agent.input` | the run's first user message; on a continuation, recovered from the transcript |
| `neatlogs.agent.output` | final assistant text, or `[<stopReason>] <message>` if the run ended abnormally |
| `neatlogs.agent.stop_reason` | only on an aborted/errored run |
| `neatlogs.error.message` | provider/abort message, when there is one |
| `neatlogs.metrics.duration_ms` | whole-run wall clock |

### CHAIN — `pi_agent.turn.N`
| Attribute | Notes |
|---|---|
| `neatlogs.chain.turn_index` | 1-based, per run |
| `neatlogs.chain.input` | the message that prompted the turn (user message, or the preceding tool results) |
| `neatlogs.chain.output` | the turn's assistant text; on a tool-calling turn, a summary of the calls it made |
| `neatlogs.chain.tool_result_count` | number of tool results fed back into the next turn |

### LLM — `pi_agent.llm.<model>`
| Attribute | Notes |
|---|---|
| `neatlogs.llm.model_name` / `provider` / `api` | from the assistant message |
| `neatlogs.llm.response_model` | present when the provider answers with a different snapshot than requested |
| `neatlogs.llm.input` + `input_messages.N.{role,content}` | the conversation as of the call, snapshotted at `message_start` |
| `neatlogs.llm.output` + `output_messages.0.{role,content}` | assistant text, or a readable tool-call summary when the turn produced only calls |
| `neatlogs.llm.tool_calls.N.{name,arguments,id}` | one entry per requested call |
| `neatlogs.llm.token_count.{prompt,completion,total,cache_read,cache_write}` | from `usage` |
| `neatlogs.llm.cost_usd` | **pi-ai's exact price for the call**, not re-derived from tokens |
| `neatlogs.llm.cost.{prompt,completion}` | the breakdown, when pi provides it |
| `neatlogs.llm.metrics.ttft_ms` | ms to the first content delta (streaming only) |
| `neatlogs.llm.is_streaming` | `true` once deltas arrive |
| `neatlogs.llm.stop_reason` | `stop` / `length` / `toolUse` / `error` / `aborted` |
| `neatlogs.error.message` | the message's `errorMessage`, when set |
| duration | opens at `message_start`, closes at `message_end` → real provider latency |

### TOOL — `pi_agent.tool.<name>`
| Attribute | Notes |
|---|---|
| `neatlogs.tool.name` / `call_id` | `call_id` is Pi's `toolCallId` — what keeps parallel calls apart |
| `neatlogs.tool.input` | the args Pi passed |
| `neatlogs.tool.output` | the full tool result |
| `neatlogs.tool.is_error` | set with an ERROR status when the tool failed |
| `neatlogs.tool.is_streaming` | set when the tool emitted partial updates |

## Three honest edge cases

1. **A run aborted at a turn boundary yields a ~0ms LLM span.** The abort landed before the request was issued, so there is no provider latency to report. The span still carries the input, `stop_reason = aborted` and an ERROR status.
2. **Zero-token LLM spans are possible.** pi-ai only fills `usage` when the stream reaches `response.completed`; a call cancelled or failed earlier legitimately reports 0 tokens and no cost. That is Pi's data, not a gap in the tracing.
3. **LLM duration is backdated to pi's own call start.** Pi emits `message_start` only once the provider's first stream event arrives, so most of the latency has already elapsed by then — the span is therefore anchored to the assistant message's `timestamp` (when pi began the model-call step) and clamped to its turn's start so a child never precedes its parent. One consequence: on the `EventStream` API (`agentLoop`), a consumer that starts iterating LONG after the call finished sees the events in one buffered burst, and since the turn span can only open when its event is finally read, the clamp pins that call's duration near zero. Iterate the stream promptly and durations are exact.

## Sessions

`identify()` attaches `neatlogs.session.id`, `neatlogs.end_user.id` and `neatlogs.end_user.metadata` to the run — see `sessions-and-end-users.md`.
