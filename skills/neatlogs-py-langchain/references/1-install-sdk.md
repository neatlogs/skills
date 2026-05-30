# Step 1: Install the Neatlogs SDK

## Action

1. Call the `detect_package_manager` tool to get the install command.
2. Run the install command for the LATEST `neatlogs` with the correct extras bracket. ALWAYS pull the newest published version (add the upgrade flag so an already-installed older version is upgraded):
   - pip: `pip install --upgrade neatlogs[<extras>]`
   - uv: `uv add --upgrade neatlogs[<extras>]`  (or `uv pip install --upgrade ...`)
   - poetry: `poetry add neatlogs[<extras>]@latest`
   Choose `<extras>`:
   - If project uses OpenAI: `neatlogs[openai]`
   - If project uses Anthropic: `neatlogs[anthropic]`
   - If project uses Google GenAI: `neatlogs[google-genai]`
   - If project uses LangChain/LangGraph: `neatlogs[langchain]`
   - If project uses CrewAI: `neatlogs[crewai]`
   - Multiple: combine with commas, e.g. `neatlogs[crewai,openai]`
3. Start installation as a background task. Do not wait for it.

## Verification

The package will be available by the time we need it. Proceed immediately.
