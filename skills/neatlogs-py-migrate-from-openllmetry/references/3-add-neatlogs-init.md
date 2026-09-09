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
   `opentelemetry.instrumentation.openai`, etc.). For
   auto-instrumentation to work, the order matters — the
   `TracerProvider` must be configured before the
   `opentelemetry.instrumentation.*` modules are imported.
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

4. **Rename `OTEL_SERVICE_NAME` to your `workflow_name`** so the
   NeatLogs dashboard's Workflow column matches what was
   previously shown in your OTel collector. If you don't, traces
   still land in NeatLogs but with the SDK default workflow name
   — confusing in side-by-side review.

## What you learn

- You now have `neatlogs.init()` running. Auto-instrumentation
  (if added later via `instrumentations=[...]` in `init()`) is
  wired up.
- `workflow_name` shows up as the Workflow column in the
  NeatLogs dashboard. Pick the same name `OTEL_SERVICE_NAME`
  had so side-by-side comparison is easier.

## OpenLLMetry-specific note

If the project uses `opentelemetry-instrumentation-*` auto-
instrumentation, the import order in your entry module is
critical. The sequence must be:

1. Configure the OTel `TracerProvider` with
   `BatchSpanProcessor` and `OTLPSpanExporter` pointing at
   NeatLogs (already done in step 2's side-by-side setup).
2. `neatlogs.init(...)`.
3. `import opentelemetry.instrumentation.openai` (or whichever
   auto-instrumentation modules you use).
4. The auto-instrumentation now routes through the OTel pipeline
   to NeatLogs.

If steps 1 and 2 are out of order, the auto-instrumentation
attaches to the default global `TracerProvider` (no-op) and
NeatLogs never sees those spans.

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

The OpenLLMetry env vars and (if Path B) the manual
`tracer.start_as_current_span` call sites are still live. This
step only adds NeatLogs; it does not remove OpenLLMetry.

## Verify BEFORE moving to step 4

1. `neatlogs.init()` is called once at the top of the entry
   module.
2. `NEATLOGS_API_KEY` is in `.env` (or in the process env).
3. `OTEL_SERVICE_NAME` matches the new `workflow_name`.
4. If the project uses `BaseSettings`, `"extra": "ignore"` is in
   the `model_config`.
5. `.env` is a superset of `.env.example` plus the NeatLogs keys.
6. The app still boots and serves traffic.
