# Step 1: Install the Neatlogs SDK

## Action

1. Call the `detect_package_manager` tool to get the install command.
2. Install the LATEST `neatlogs`. ALWAYS pull the newest published version (use the upgrade flag so an already-installed older version is upgraded):
   - pip: `pip install --upgrade neatlogs`
   - uv: `uv add --upgrade neatlogs`  (or `uv pip install --upgrade neatlogs`)
   - poetry: `poetry add neatlogs@latest`
3. No extras bracket is needed for CrewAI — `neatlogs.wrap(crew)` patches the crew's agents/tasks/tools and `LLM.call` directly, so there is no separate provider instrumentor to install.
4. Start installation as a background task. Do not wait for it.

## Verification

The package will be available by the time we need it. Proceed immediately.
