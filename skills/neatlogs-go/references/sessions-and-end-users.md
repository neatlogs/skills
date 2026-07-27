# Sessions & End-Users

## Why

Attaching a **session** (the conversation) and an **end-user** (your app's user)
to traces turns raw telemetry into customer analytics: slice usage, cost,
latency, and errors per user and segment; view a multi-turn conversation as one
timeline; and replay a specific customer's conversation when they reach out.

## The model

- **One turn = one trace.** A **session** groups the turns of a conversation.
- **End-user is per session** — the same end-user on every turn.
- Identity is set on `ctx` and stamped on the **trace root**; the backend rolls
  it up. It is **never** set on `Init` (it is per-request, not process-global).
- `Init`'s config has no session/end-user field; the operator/service is implied
  by the workflow, not an end-user id.

## `Identify` — the one mechanism

`neatlogs.Identify` binds identity onto a `context.Context` and returns a new
`ctx`. Anything that runs under that `ctx` inherits it — `neatlogs.Trace`, the
`WrapGenAI` auto-root, and the explicit span helpers (`StartLLMSpan`,
`StartRetrieverSpan`, `StartToolSpanFromHeaders`). The identity processor stamps
it on the trace **root** only. There is nothing else to call.

```go
ctx = neatlogs.Identify(ctx, neatlogs.IdentifyOptions{
    SessionID:       "conv_123",                 // same id every turn → one session
    EndUserID:       "u_456",                    // the customer's end-user
    EndUserMetadata: map[string]any{"plan": "pro"},
})
```

`IdentifyOptions` fields: `SessionID string`, `EndUserID string`,
`EndUserMetadata map[string]any`. Only non-empty fields are applied.

## Multi-turn example (Gemini via `WrapGenAI`)

Re-bind identity at the start of each turn (same `SessionID` + `EndUserID`),
then run the turn under that `ctx`:

```go
gc := nlgenai.WrapGenAI(client) // from contrib/genai
sessionID := "conv_123"

for _, msg := range conversation {
    turnCtx := neatlogs.Identify(ctx, neatlogs.IdentifyOptions{
        SessionID:       sessionID,        // reused every turn → grouped session
        EndUserID:       "u_456",
        EndUserMetadata: map[string]any{"plan": "pro"},
    })
    resp, err := gc.GenerateContent(turnCtx, "gemini-2.5-flash", contentsFor(msg), cfg)
    _ = resp
    _ = err
}
```

Each `GenerateContent` is its own trace; all carry `SessionID: conv_123` +
`EndUserID: u_456`, so the backend groups them into one session for that user.

## Direct provider / boundary spans

Same call — bind identity on `ctx`, then open the span under it; the auto-root
inherits the session + end-user via the identity processor:

```go
turnCtx := neatlogs.Identify(ctx, neatlogs.IdentifyOptions{SessionID: "conv_123", EndUserID: "u_456"})
_, llm := neatlogs.StartLLMSpan(turnCtx, neatlogs.LLMCallOptions{Provider: "openai", Model: "gpt-5.5", Messages: msgs})
defer llm.End()
```

`StartToolSpanFromHeaders` also takes `IdentifyOptions` directly, so a service
boundary can continue the inbound trace and bind identity in one call.

## Custom `Trace` roots

If you open your own root, run it under the `Identify`-derived ctx:

```go
ctx = neatlogs.Identify(ctx, neatlogs.IdentifyOptions{SessionID: "conv_123", EndUserID: "u_456"})
ctx, span, end := neatlogs.Trace(ctx, "chat_turn")
defer end()
```

## Dashboard

Filter traces by **Session** to see a whole conversation, or by **End-user** to
see everything one customer's end-user did. `EndUserMetadata` fields are
filterable too.
