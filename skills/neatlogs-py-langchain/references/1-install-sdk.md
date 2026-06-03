# Step 1: Install the Neatlogs SDK

## Action

1. Call the `detect_package_manager` tool to get the install command.
2. Install the LATEST `neatlogs`. ALWAYS pull the newest published version (use the upgrade flag so an already-installed older version is upgraded):
   - pip: `pip install --upgrade neatlogs`
   - uv: `uv add --upgrade neatlogs`  (or `uv pip install --upgrade neatlogs`)
   - poetry: `poetry add neatlogs@latest`
3. The LangChain callback handler needs `langchain-core` (already present in any LangChain/LangGraph project). The only extra worth adding is the **embedding provider** instrumentor IF the project produces embeddings through a provider class (`OpenAIEmbeddings` → `neatlogs[openai]`, `CohereEmbeddings` → `neatlogs[cohere]`) — see step 7.5. The handler itself needs no extras bracket.
4. Start installation as a background task. Do not wait for it.

## Verification

The package will be available by the time we need it. Proceed immediately.
