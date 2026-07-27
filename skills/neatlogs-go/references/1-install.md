# Step 1: Install the Neatlogs Go SDK

## Action

1. Requires **Go 1.25+**. Confirm with `go version`.
2. Add the SDK to the module:

   ```sh
   go get github.com/neatlogs/neatlogs-go
   ```

3. For **Gemini**, the `WrapGenAI` wrapper lives in a **separate module** (`contrib/genai`) so its heavy `genai` dependency stays out of apps that don't wrap Gemini. Add it and the genai client:

   ```sh
   go get github.com/neatlogs/neatlogs-go/contrib/genai
   go get google.golang.org/genai
   ```

   Import it under its own path (commonly aliased `nlgenai`):

   ```go
   import nlgenai "github.com/neatlogs/neatlogs-go/contrib/genai"
   ```

> **Do NOT use `contrib/adk`.** The Google ADK integration is deprecated and non-functional under the private-provider design (ADK binds to the global OTel provider Neatlogs no longer owns). Instrument model calls and boundaries explicitly instead.

## Verification

Run `go mod tidy` and confirm `github.com/neatlogs/neatlogs-go` (and, if using Gemini, `github.com/neatlogs/neatlogs-go/contrib/genai` + `google.golang.org/genai`) appear in `go.mod`. Proceed to Step 2.
