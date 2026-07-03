# Step 5: Trace custom code

Wrap any block of your own code (handlers, tools, pipeline stages) in a span with
`neatlogs.Trace`. It returns a **new ctx**, the span, and an `end` func.

```go
ctx, span, end := neatlogs.Trace(ctx, "handle_request")
defer end()
_ = span
```

## The rules

- `defer end()` immediately — it closes the span when the function returns.
- **Pass the returned `ctx` to children.** Nesting is by context: a `Trace` (or a
  `WrapGenAI` / ADK call) that receives this `ctx` becomes a **child** of this
  span. Reuse the old ctx instead and the child ends up detached.

## Nested example

```go
func handleRequest(ctx context.Context, gc *neatlogs.GenAIModels, req Request) error {
    ctx, _, end := neatlogs.Trace(ctx, "handle_request") // root for this request
    defer end()

    // child span — receives the request ctx, so it nests under handle_request
    parsed, err := parseInput(ctx, req)
    if err != nil {
        return err
    }

    // LLM call under the same ctx → also a child of handle_request
    _, err = gc.GenerateContent(ctx, "gemini-2.5-flash", parsed.Contents, parsed.Cfg)
    return err
}

func parseInput(ctx context.Context, req Request) (Parsed, error) {
    ctx, _, end := neatlogs.Trace(ctx, "parse_input")
    defer end()
    // ... use ctx for anything deeper ...
    return doParse(ctx, req)
}
```

## WRONG vs RIGHT

```go
// ❌ WRONG — ignoring the returned ctx. Children use the old ctx and don't nest.
_, _, end := neatlogs.Trace(ctx, "handle_request")
defer end()
parseInput(ctx, req) // still the OUTER ctx → parse_input is not a child
```

```go
// ✅ RIGHT — thread the returned ctx into every child call.
ctx, _, end := neatlogs.Trace(ctx, "handle_request")
defer end()
parseInput(ctx, req) // nests correctly
```

## Verify

Every `neatlogs.Trace` is followed by `defer end()`, and the ctx it returns is
the one handed to any nested `Trace` / LLM / ADK call.
