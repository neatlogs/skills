# Step 1: Install neatlogs (latest)

## Action

1. Call `detect_package_manager` to get the install command.
2. Install the LATEST `neatlogs` + the Pydantic AI extra (always pull newest; add the upgrade flag):
   - pip: `pip install --upgrade neatlogs pydantic-ai`
   - uv: `uv add --upgrade neatlogs pydantic-ai`
   - poetry: `poetry add neatlogs@latest pydantic-ai`
3. Start installation as a background task; continue immediately.

## Verification
`neatlogs` appears in the project dependencies.
