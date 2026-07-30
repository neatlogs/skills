# Step 3: Set environment variables

## Action

Set these in the process environment (shell, `.env`, Docker, systemd, CI):

| Var                            | Required | Purpose                                                              |
| ------------------------------ | -------- | -------------------------------------------------------------------- |
| `NEATLOGS_API_KEY`             | Yes      | Auth for span export. Without it, spans are not exported.            |
| `GOOGLE_API_KEY` / `GEMINI_API_KEY` | Gemini only | Auth for the genai client (either name works).                |

## Env fallback

`Config.APIKey` falls back to `NEATLOGS_API_KEY` if left empty. Passing it explicitly via `os.Getenv("NEATLOGS_API_KEY")` in `Config` is still preferred — it works identically in Docker, CI, and cron where env load order can vary.

## Example

```sh
export NEATLOGS_API_KEY="nl_..."
export GOOGLE_API_KEY="..."       # only if using Gemini
```

## Verify

`echo $NEATLOGS_API_KEY` returns a value in the same shell/process that runs the app.
