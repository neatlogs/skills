# Step 3: Set Environment Variables

1. `set_env_values`: `NEATLOGS_API_KEY`.
2. Preserve `.env.example` keys. Strands' `BedrockModel` needs AWS creds: `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` (or a profile). `.env` is a superset.
3. `.env` gitignored.
