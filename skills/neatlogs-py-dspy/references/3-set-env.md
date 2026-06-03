# Step 3: Set Environment Variables

1. `set_env_values`: write `NEATLOGS_API_KEY` (+ `NEATLOGS_ENDPOINT` if provided).
2. Preserve all existing `.env.example` keys (e.g. `OPENAI_API_KEY` for `dspy.LM("openai/...")`). `.env` is a superset.
3. Ensure `.env` is gitignored.
