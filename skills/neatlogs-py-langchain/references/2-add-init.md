# Step 2: Add neatlogs.init()

## Action

1. Find the application entry point (`main.py`, `app.py`, `run.py`, or `if __name__ == "__main__":`)
2. Read the entry point file.
3. Add `import os` and `import neatlogs` near the top.
4. Add the init call. For LangChain, `init()` takes NO `instrumentations=["langchain"]` — tracing is done by the callback handler (Step 4). Only add a provider instrumentor for embeddings (e.g. `instrumentations=["openai"]`) if the project embeds through a provider class — see step 7.5.

## Pattern

```python
import os
import neatlogs
from dotenv import load_dotenv  # if project uses dotenv

load_dotenv()  # MUST be before init()

neatlogs.init(
    api_key=os.getenv("NEATLOGS_API_KEY"),
    workflow_name="{project_name}",
)

# ALL LangChain library imports MUST come AFTER this point
from langchain_openai import ChatOpenAI  # etc.
```

## WRONG vs RIGHT

```python
# ❌ WRONG — missing api_key. SDK may not find it from env depending on load order.
neatlogs.init(
    workflow_name="myapp",
)

# ✅ RIGHT — explicit api_key from env var guarantees it works.
neatlogs.init(
    api_key=os.getenv("NEATLOGS_API_KEY"),
    workflow_name="myapp",
)
```

```python
# ❌ WRONG — instrumentations=["langchain"]. The callback handler is the path now;
# listing "langchain" here would double-fire chain/LLM spans alongside the handler.
neatlogs.init(api_key=..., workflow_name="myapp", instrumentations=["langchain", "openai"])

# ✅ RIGHT — no "langchain"; attach the handler in Step 4. (Keep "openai" ONLY if you
# need provider-level embedding capture — see step 7.5.)
neatlogs.init(api_key=..., workflow_name="myapp")
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

1. Grep the file for `api_key=os.getenv("NEATLOGS_API_KEY")`. If this string does not appear inside `neatlogs.init(...)`, you did this step wrong. Fix it now.
2. Confirm `init()` has NO `"langchain"` in `instrumentations=` — LangChain is traced by the handler (Step 4). A provider key (`"openai"`/`"cohere"`) is allowed ONLY for embedding capture (step 7.5).
