# Step 1: Install the Neatlogs Go SDK

## Action

1. Requires **Go 1.25+**. Confirm with `go version`.
2. Add the SDK to the module:

   ```sh
   go get github.com/neatlogs/neatlogs-go
   ```

3. The Google ADK helper is a **submodule** of the same module — it comes with the `go get` above; you just import it under its own path (commonly aliased `nladk`):

   ```go
   import nladk "github.com/neatlogs/neatlogs-go/contrib/adk"
   ```

4. For **Gemini**, the genai client is a peer dependency — add it too:

   ```sh
   go get google.golang.org/genai
   ```

## Verification

Run `go mod tidy` and confirm `github.com/neatlogs/neatlogs-go` (and `google.golang.org/genai` if using Gemini) appear in `go.mod`. Proceed to Step 2.
