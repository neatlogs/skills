# Step 2: Add neatlogs.init()

## Action

1. Find the entry point (`main.py` / `if __name__ == "__main__":`, or the app module for servers).
2. Add `import os` and `import neatlogs` at the top.
3. If `load_dotenv()` is used, call it BEFORE `init()`.
4. Call `init()` BEFORE importing `pydantic_ai` (so wrap()'s class-level Model/tool hooks patch at the right time). Import the agent module with a deferred import after init when needed.

```python
import os
import neatlogs
from dotenv import load_dotenv

load_dotenv()
neatlogs.init(
    api_key=os.getenv("NEATLOGS_API_KEY"),
    workflow_name="my-pydantic-ai-app",
)

# import the agent AFTER init
from .agent import research_agent
```

## CRITICAL: web servers (FastAPI/Flask/ASGI)
For a web app, `init()` must live in the **module the server imports** (the one defining `app`), before that module imports `pydantic_ai` — NOT in a `main.py` launcher the worker never runs.

## NOTE on instrumentations
You do NOT need `instrumentations=[...]` for Pydantic AI — `neatlogs.wrap(agent)` (Step 4) installs the hooks. Only add `instrumentations=["openai"]` etc. if the app ALSO calls a provider SDK directly outside Pydantic AI.
