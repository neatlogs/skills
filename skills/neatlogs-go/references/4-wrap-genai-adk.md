# Step 4: Capture LLM calls (Gemini & Google ADK)

Two paths depending on how the app calls the model. Do the one(s) that apply.

## A. Gemini via `WrapGenAI`

Wrap a `*genai.Client` (from `google.golang.org/genai`) once, then call the
wrapped client **exactly like the raw one** — every `GenerateContent` becomes a
traced LLM span with prompt/response text.

```go
import (
    "github.com/neatlogs/neatlogs-go"
    "google.golang.org/genai"
)

client, err := genai.NewClient(ctx, &genai.ClientConfig{
    APIKey:  os.Getenv("GOOGLE_API_KEY"),
    Backend: genai.BackendGeminiAPI,
})
if err != nil {
    log.Fatal(err)
}

gc := neatlogs.WrapGenAI(client) // wrap once

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

### Reasoning-model note (important)

`gemini-2.5-flash` is a **reasoning model** — its thinking tokens count against
`MaxOutputTokens`. Keep `MaxOutputTokens` **generous** (e.g. `2048`), not small
(`256`), or the model spends the budget on hidden reasoning and the visible
output gets truncated or comes back empty.

## B. Google ADK

`neatlogs.Init` registers the **global** OTel TracerProvider, and Google ADK
emits its own spans through that provider — so ADK's trace **structure is
captured automatically**. Do **NOT** wrap ADK for structure; there is nothing to
wrap for the tree.

The one gap: ADK records message **text** on OTel *logs*, not on spans — so the
auto-captured spans have tokens/model/tools but not the prompt/response text. To
also record that text on the span, wrap the **model**:

```go
import nladk "github.com/neatlogs/neatlogs-go/contrib/adk"

model = nladk.WrapModel(model) // adds I/O text capture to ADK's generate_content span
```

`WrapModel` is **I/O capture only** — it attaches prompt/response text onto ADK's
existing `generate_content` span. It is **NOT** an auto-root: ADK still creates
the root span. Use it purely to fill in the missing message text.

## Verify

- Gemini: calls go through `gc` (the wrapped client), not the raw `client`.
- ADK: no wrapping added for structure; `WrapModel` used only if you need message
  text on spans.
