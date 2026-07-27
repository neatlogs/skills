# Step 4: Capture LLM calls (Gemini & direct providers)

Pick the path(s) that match how the app calls models. The Go SDK uses a
**private provider**, so nothing is auto-captured — every model call is
instrumented explicitly.

## A. Gemini via `WrapGenAI`

Wrap a `*genai.Client` (from `google.golang.org/genai`) once, then call the
wrapped client **exactly like the raw one** — every `GenerateContent` becomes a
traced LLM span with prompt/response text under an auto `workflow` root.
`WrapGenAI` lives in the `contrib/genai` module (alias it `nlgenai`):

```go
import (
    "github.com/neatlogs/neatlogs-go"
    nlgenai "github.com/neatlogs/neatlogs-go/contrib/genai"
    "google.golang.org/genai"
)

client, err := genai.NewClient(ctx, &genai.ClientConfig{
    APIKey:  os.Getenv("GOOGLE_API_KEY"),
    Backend: genai.BackendGeminiAPI,
})
if err != nil {
    log.Fatal(err)
}

gc := nlgenai.WrapGenAI(client) // wrap once

temp := float32(0.7)
resp, err := gc.GenerateContent(ctx, "gemini-2.5-flash",
    []*genai.Content{{
        Role:  genai.RoleUser,
        Parts: []*genai.Part{{Text: "Explain goroutines in one sentence."}},
    }},
    &genai.GenerateContentConfig{
        Temperature:       &temp,
        MaxOutputTokens:   2048,
        SystemInstruction: &genai.Content{Parts: []*genai.Part{{Text: "You are concise."}}},
    },
)
```

`GenerateContent`, `GenerateContentStream`, `EmbedContent`, and `CountTokens` are
traced; any other method is reachable via `gc.Raw()`.

### Reasoning-model note (important)

`gemini-2.5-flash` is a **reasoning model** — its thinking tokens count against
`MaxOutputTokens`. Keep `MaxOutputTokens` **generous** (e.g. `2048`), not small
(`256`), or the model spends the budget on hidden reasoning and the visible
output gets truncated or comes back empty.

## B. Direct provider calls via `StartLLMSpan`

For OpenAI / Anthropic / any provider `WrapGenAI` doesn't cover, open an LLM span
you fill in. It auto-roots under a `workflow` span when there's no active parent.

```go
ctx, llm := neatlogs.StartLLMSpan(ctx, neatlogs.LLMCallOptions{
    Provider: "openai",              // neatlogs provider id
    Model:    "gpt-5.5",
    Messages: []neatlogs.LLMMessage{
        {Role: "system", Content: "You are concise."},
        {Role: "user", Content: "Explain goroutines in one sentence."},
    },
    // MaxTokens / Temperature / TopP / Streaming are optional.
})
defer llm.End()

// ... make the real provider call ...
llm.SetOutputMessage("assistant", out)
llm.SetUsage(promptTok, completionTok, totalTok)
llm.SetFinishReason("stop")
// llm.SetModel / llm.SetProvider allow a post-call override (alias / fallback).
```

Span name defaults to `"{provider}.chat"`; override with `LLMCallOptions.Name`.

## Do NOT use `contrib/adk`

The Google ADK integration (`contrib/adk`, `WrapModel`, A2A helpers) is
**deprecated and non-functional**. It relied on `Init` registering the global
OTel provider so ADK's own spans flowed through — but the SDK now uses a private
provider and never touches global OTel state, so ADK spans never reach Neatlogs.
There is no drop-in replacement for automatic ADK capture; instrument the model
calls the agent makes with `StartLLMSpan`, and boundaries with `StartSpan` /
`StartToolSpanFromHeaders`.

## Verify

- Gemini: calls go through `gc` (the wrapped client), not the raw `client`, and
  `WrapGenAI` is imported from `contrib/genai` (aliased `nlgenai`).
- Direct providers: every model call is bracketed by `StartLLMSpan` … `llm.End()`
  with output + usage set.
- No `contrib/adk` import anywhere.
