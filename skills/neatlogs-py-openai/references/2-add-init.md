# Step 2: Add neatlogs.init()

## Action

1. Find the application entry point (`main.py`, `app.py`, `run.py`, or `if __name__ == "__main__":`).
   **For web servers (FastAPI/Flask/Starlette/Litestar) read the CRITICAL section below FIRST — the entry point is NOT the file you think.**
2. Read the entry point file.
3. Add `import os` and `import neatlogs` near the top.
4. Add the init call. Use the `detect_stack` tool to get the `instrumentations` list.

## CRITICAL: Web servers (FastAPI / Flask / ASGI / WSGI)

For a web app, the server (uvicorn/gunicorn/hypercorn) imports the **app module** (e.g. `src.app:app`) in its own worker process. A `main.py` that calls `uvicorn.run("src.app:app", ...)` does NOT run in that worker — so putting `init()` in `main.py` means **the process that actually serves requests never initializes Neatlogs, and no traces are produced.**

`init()` MUST go in the **module that defines the app object** (the one the server imports), and it MUST run BEFORE that module imports the LLM SDK.

```python
# ❌ WRONG — init() in main.py / the uvicorn launcher.
# uvicorn imports src.app:app in a separate worker that never runs this. No traces.
# main.py
neatlogs.init(...)
uvicorn.run("src.app:app", reload=True)

# app.py  ← what the worker actually loads
import anthropic          # imported with NO init having run → instrumentor never patches it
app = FastAPI(lifespan=lifespan)
```

```python
# ✅ RIGHT — init() at the top of app.py (the imported app module), BEFORE the LLM import.
# app.py
import os
import neatlogs
from dotenv import load_dotenv

load_dotenv()
neatlogs.init(
    api_key=os.getenv("NEATLOGS_API_KEY"),
    workflow_name="my-api",
    instrumentations=["anthropic"],   # from detect_stack
)

import anthropic                      # now patched correctly
from fastapi import FastAPI
app = FastAPI(lifespan=lifespan)
```

Rules for web apps:
- Put `init()` in the app module (where `app = FastAPI(...)` / `Flask(__name__)` lives), at the very top, after `load_dotenv()`, before the LLM SDK import.
- Do NOT put `init()` only in a `main.py` whose job is to call `uvicorn.run(...)`. If such a `main.py` also matters (e.g. someone runs it directly), it's harmless to leave its own init too, but the app-module init is the one that counts.
- `neatlogs.flush()`/`shutdown()` go in the lifespan shutdown / `atexit` (Step 7) — but they only work if `init()` ran in the SAME process, which the above guarantees.

## Pattern (non-web: CLI / script / worker)

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

1. Grep for `api_key=os.getenv("NEATLOGS_API_KEY")`. If this string does not appear inside `neatlogs.init(...)`, you did this step wrong. Fix it now.
2. **Web apps:** confirm `init()` is in the module that defines the app object (the one the server imports), BEFORE the LLM SDK import — NOT only in a `uvicorn.run(...)` launcher. Grep the app module for `neatlogs.init`; if it's missing there, the served process won't trace.
