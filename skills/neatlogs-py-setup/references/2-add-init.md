# Step 2: Add neatlogs.init()

## Action

1. Find the application entry point (`main.py`, `app.py`, `run.py`, or `if __name__ == "__main__":`)
2. Read the entry point file.
3. Add `import os` and `import neatlogs` near the top.
4. Add the init call. For the wrap()/handler/processor paths, `init()` takes NO `instrumentations=` argument — instrumentation happens by wrapping the client/agent (or attaching the handler/processor). Only add `instrumentations=[...]` for a provider `wrap()` doesn't cover (Groq/Cohere/Bedrock/Mistral/Together/LiteLLM) or for embedding capture.

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

# ALL LLM/framework imports MUST come AFTER this point; wrap the client/agent next.
from openai import OpenAI  # etc.
client = neatlogs.wrap(OpenAI())
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
# ❌ WRONG — listing a provider in instrumentations= AND wrapping its client. Double-fires.
neatlogs.init(api_key=..., instrumentations=["openai"])
client = neatlogs.wrap(OpenAI())

# ✅ RIGHT — wrap() only; no instrumentations= for a wrap()-supported provider.
neatlogs.init(api_key=...)
client = neatlogs.wrap(OpenAI())
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

Do NOT pass `endpoint=` — the SDK defaults to the production cloud endpoint.

## Verify BEFORE moving to step 3

1. Grep the file for `api_key=os.getenv("NEATLOGS_API_KEY")`. If this string does not appear inside `neatlogs.init(...)`, you did this step wrong. Fix it now.
2. Confirm `init()` has NO `instrumentations=` for a provider you intend to `wrap()`. Only uncovered providers / embedding capture belong there.
