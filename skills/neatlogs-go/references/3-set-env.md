# Step 3: Set environment variables

## Action

Set these in the process environment (shell, `.env`, Docker, systemd, CI):

| Var                            | Required | Purpose                                                              |
| ------------------------------ | -------- | -------------------------------------------------------------------- |
| `NEATLOGS_API_KEY`             | Yes      | Auth for span export. Without it, spans are not exported.            |
| `NEATLOGS_ENDPOINT`            | No       | Base URL (no `/v1/traces`). Omit for the managed Neatlogs cloud.     |
| `GOOGLE_API_KEY` / `GEMINI_API_KEY` | Gemini only | Auth for the genai client (either name works).                |

## Env fallbacks

`Config.APIKey` and `Config.Endpoint` fall back to env if left empty:

- `APIKey` empty → SDK reads `NEATLOGS_API_KEY`.
- `Endpoint` empty → SDK reads `NEATLOGS_ENDPOINT`, else defaults to the managed cloud.

Passing them explicitly via `os.Getenv(...)` in `Config` is still preferred — it works identically in Docker, CI, and cron where env load order can vary.

## Example

```sh
export NEATLOGS_API_KEY="nl_..."
export GOOGLE_API_KEY="..."       # only if using Gemini
# export NEATLOGS_ENDPOINT="https://staging-cloud.neatlogs.com"   # only for self-hosted/staging
```

## Verify

`echo $NEATLOGS_API_KEY` returns a value in the same shell/process that runs the app.
