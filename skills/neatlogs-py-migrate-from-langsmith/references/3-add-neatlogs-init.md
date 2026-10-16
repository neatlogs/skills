# Step 3: Add `neatlogs.init()`

## Action

1. Pick the right entry module — the one under
   `if __name__ == "__main__":` or the one referenced by the main
   CLI command. If unclear, run:
   ```bash
   git grep -lE 'if __name__ == .__main__' -- '*.py' 2>/dev/null | head -1
   ```
2. Add the import + init at the **top** of the entry module, BEFORE
   any LLM SDK import (`openai`, `anthropic`, `langchain`,
   `langchain_community`, `crewai`, etc.). For auto-instrumentation
   to work, the order matters.
3. Load `.env` BEFORE `init()` if the project uses one.

```python
# Top of entry.py
import os
import neatlogs

# Load .env BEFORE init() so NEATLOGS_API_KEY is in env.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # ok if the project doesn't use dotenv

neatlogs.init(
    api_key=os.getenv("NEATLOGS_API_KEY"),  # explicit even though init() also reads env
    workflow_name="my-app",                # REPLACE with your service's name
)
```

4. **Rename `LANGCHAIN_PROJECT` / `LANGSMITH_PROJECT` to your
   `workflow_name`** so the NeatLogs dashboard's Workflow column
   matches what was previously shown in LangSmith's project column.
   If you don't, traces still land in NeatLogs but with the SDK
   default workflow name — confusing in side-by-side review.

## What you learn

- You now have `neatlogs.init()` running. Auto-instrumentation
  (if added later via `instrumentations=[...]` in `init()`) is
  wired up.
- `workflow_name` shows up as the Workflow column in the NeatLogs
  dashboard. Pick the same name `LANGCHAIN_PROJECT` /
  `LANGSMITH_PROJECT` had so side-by-side comparison is easier.

## LangChain-specific note

If the project uses LangChain, you have two ways to wire
NeatLogs to LangChain's runtime:

### Option 1: OTel exporter (recommended — same as Langfuse Path A)

The LangChain `langchain.observability` callback (v0.3+) uses
the global OTel tracer. If `OTEL_EXPORTER_OTLP_ENDPOINT` points
at NeatLogs in step 4, LangChain spans flow through to NeatLogs
without any extra wiring. This is the default and what the skill
recommends.

### Option 2: `neatlogs.langchain_handler()` callback

If for some reason the OTel route doesn't work for the project
(e.g. a custom TracerProvider that doesn't pick up the env var),
use the explicit callback:

```python
from langchain_core.tracers import LangChainTracer
from langchain.observability import enable_tracing

# Create the NeatLogs LangChain handler.
neatlogs_handler = neatlogs.langchain_handler()

# Register it as a LangChain callback.
# (The exact API depends on LangChain version; check your version's
# `langchain.observability` or `langchain.tracing` docs.)
```

The first option is simpler and what the rest of this skill
assumes. The second option is a fallback.

## Common crash: Pydantic-Settings + extra env vars

If the project uses `pydantic-settings` (class extends
`BaseSettings`) and reads from `.env`, adding `NEATLOGS_API_KEY=...`
to `.env` can crash the app on import with "extra fields not
permitted". Fix:

```python
# ❌ WRONG
class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

# ✅ RIGHT
class Settings(BaseSettings):
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",   # ← required after adding NEATLOGS_*
    }
```

If `model_config` uses `SettingsConfigDict`:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
```

## Carry over ALL `.env.example` keys

If the project has a `.env.example` or `.env.sample`, copy EVERY
key into `.env` — provider keys (`OPENAI_API_KEY`,
`ANTHROPIC_API_KEY`, `LANGCHAIN_API_KEY`), app secrets
(`API_SECRET_KEY`), server config (`HOST`, `PORT`, `ENV`),
service URLs (`REDIS_URL`, `DATABASE_URL`), feature flags.
Dropping any of these can break the app. The new `.env` is a
**superset** of `.env.example` plus the NeatLogs keys.

## Side-by-side still in effect

The LangSmith / LangChain env vars and (if Path B) the LangSmith
SDK call sites are still live. This step only adds NeatLogs; it
does not remove LangSmith.

## Verify BEFORE moving to step 4

1. `neatlogs.init()` is called once at the top of the entry
   module.
2. `NEATLOGS_API_KEY` is in `.env` (or in the process env).
3. `LANGCHAIN_PROJECT` / `LANGSMITH_PROJECT` matches the new
   `workflow_name`.
4. If the project uses `BaseSettings`, `"extra": "ignore"` is in
   the `model_config`.
5. `.env` is a superset of `.env.example` plus the NeatLogs keys.
6. The app still boots and serves traffic.
