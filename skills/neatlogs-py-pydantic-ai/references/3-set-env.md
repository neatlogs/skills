# Step 3: Set Environment Variables

1. Use `set_env_values` to write `NEATLOGS_API_KEY` to `.env`.
2. Preserve every existing `.env.example` key (provider keys like `OPENAI_API_KEY`, config). The `.env` must be a superset.
3. Ensure `.env` is in `.gitignore`.

Pydantic AI reads the provider key from the standard env var (e.g. `OPENAI_API_KEY` for `openai:gpt-4o-mini`).
