# Step 1: Install the Neatlogs SDK

## Action

1. Call the `detect_package_manager` tool to get the install command.
2. Install the LATEST `neatlogs`. ALWAYS pull the newest published version (use the upgrade flag so an already-installed older version is upgraded):
   - pip: `pip install --upgrade neatlogs`
   - uv: `uv add --upgrade neatlogs`  (or `uv pip install --upgrade neatlogs`)
   - poetry: `poetry add neatlogs@latest`
3. **Add the extras bracket for every auto-instrumentor provider in the detected `instrumentations` list.** Call `detect_stack` to get `instrumentations`, then install `neatlogs[<extras>]` where `<extras>` are the providers that rely on the GLOBAL auto-instrumentor (not `wrap()`):
   - Include in the bracket: `bedrock`, `groq`, `cohere`, `mistralai`, `litellm`, `google-genai`, `vertexai`, `agno`, `dspy`, `crewai`, `langchain`, `langgraph`, `llama-index`, `google-adk`, `haystack`, `instructor`, `mcp`, `milvus`, `guardrails` — whichever appear in the detected list.
   - Do NOT bracket `openai`/`anthropic` when they're used via `neatlogs.wrap(client)` (wrap needs no extra). Only bracket `openai`/`cohere` if the app produces embeddings through that provider class (see `references/auto-instrumented.md`).
   - Map underscores to hyphens for the extra name (`google_genai` → `google-genai`).
   - Example: detected `instrumentations=["openai","google_genai","bedrock"]` where openai is wrapped → install `neatlogs[google-genai,bedrock]`.
   - Why it matters: the openinference adapters ship in neatlogs base, but each extra pulls the provider's UNDERLYING library (e.g. `bedrock`→`boto3`). On a repo that already has that library it's a no-op, but the bracket guarantees the instrumentor can load everywhere.
   - Commands (quote the bracket so the shell doesn't glob it): `uv add --upgrade "neatlogs[google-genai,bedrock]"` / `pip install --upgrade "neatlogs[google-genai,bedrock]"` / `poetry add "neatlogs[google-genai,bedrock]@latest"`.
4. Start installation as a background task. Do not wait for it.

## Verification

The package will be available by the time we need it. Proceed immediately.
