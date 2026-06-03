# Step 1: Install the Neatlogs SDK

## Action

1. Call the `detect_package_manager` tool to get the install command.
2. Install the LATEST `neatlogs`. ALWAYS pull the newest published version (use the upgrade flag so an already-installed older version is upgraded):
   - pip: `pip install --upgrade neatlogs`
   - uv: `uv add --upgrade neatlogs`  (or `uv pip install --upgrade neatlogs`)
   - poetry: `poetry add neatlogs@latest`
3. No extras bracket is needed — the trace processor reads the OpenAI Agents SDK's own tracing events (the `agents` package is already a project dependency). There is no separate instrumentor to install.
4. Start installation as a background task. Do not wait for it.

## Verification

The package will be available by the time we need it. Proceed immediately.
