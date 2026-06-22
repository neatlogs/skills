# Step 3: Set Environment Variables

1. `set_env_values`: `NEATLOGS_API_KEY` (+ `NEATLOGS_ENDPOINT` if provided).
2. Preserve all `.env.example` keys. Hermes routes LLM calls through OpenRouter by
   default, so `OPENROUTER_API_KEY` is typically required to run the agent. `.env`
   is a superset.
3. `.env` gitignored.
