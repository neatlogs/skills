# Step 2: Add neatlogs.init()

## Action

1. Find the application entry point (`main.py`, `app.py`, `run.py`, or `if __name__ == "__main__":`)
2. Read the entry point file.
3. Add `import os` and `import neatlogs` near the top.
4. Add the init call. Use the `detect_stack` tool to get the `instrumentations` list.

## Pattern

```python
import os
import neatlogs
from dotenv import load_dotenv  # if project uses dotenv

load_dotenv()  # MUST be before init()

neatlogs.init(
    api_key=os.getenv("NEATLOGS_API_KEY"),
    workflow_name="{project_name}",
    instrumentations={detected_instrumentations},  # from detect_stack tool
)

# ALL LLM library imports MUST come AFTER this point
from openai import OpenAI  # etc.
```

## WRONG vs RIGHT

```python
# ❌ WRONG — missing api_key. SDK may not find it from env depending on load order.
neatlogs.init(
    workflow_name="myapp",
    instrumentations=["openai"],
)

# ✅ RIGHT — explicit api_key from env var guarantees it works.
neatlogs.init(
    api_key=os.getenv("NEATLOGS_API_KEY"),
    workflow_name="myapp",
    instrumentations=["openai"],
)
```

```python
# ❌ WRONG — no import os
import neatlogs
neatlogs.init(api_key=os.getenv("NEATLOGS_API_KEY"), ...)  # NameError!

# ✅ RIGHT — import os before using os.getenv
import os
import neatlogs
neatlogs.init(api_key=os.getenv("NEATLOGS_API_KEY"), ...)
```

## Why api_key is required

The SDK CAN read NEATLOGS_API_KEY from env internally, but only if `load_dotenv()` ran first AND the env var is available in the process. Passing it explicitly guarantees it works in all cases: Docker, CI, systemd, cron, and projects that don't use dotenv.

## Do NOT pass endpoint=

Leave `endpoint=` out of `init()`. The SDK defaults to the managed Neatlogs cloud, which is correct for production. Self-hosted/staging/local backends are a deployment concern configured outside the application code — do not bake an endpoint into the source.

## Verify BEFORE moving to step 3

Grep the file for `api_key=os.getenv("NEATLOGS_API_KEY")`. If this string does not appear inside `neatlogs.init(...)`, you did this step wrong. Fix it now.
