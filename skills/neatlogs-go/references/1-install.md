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

4. For **Google ADK**, install the explicit private-provider integration:

   ```sh
   go get github.com/neatlogs/neatlogs-go/contrib/adk
   ```

   Import it separately (commonly aliased `nladk`):

   ```go
   import nladk "github.com/neatlogs/neatlogs-go/contrib/adk"
   ```

   This is not global OTel auto-instrumentation. The application must use
   `nladk.InstrumentConfig(...)` and `nladk.Run(...)` as described in Step 4.

## Verification

Run `go mod tidy` and confirm `github.com/neatlogs/neatlogs-go` plus each selected integration module (`contrib/genai` for Gemini and/or `contrib/adk` for Google ADK) appear in `go.mod`. Keep the root and selected contrib modules on the same released version. Proceed to Step 2.
