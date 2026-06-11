# Step 3: Set Environment Variables

## Action

1. Use the `set_env_values` tool to write these to `.env`:
   - `NEATLOGS_API_KEY` — use the API key value provided in the wizard session context
2. Verify `.env` is in `.gitignore`. If not, add it.
3. **Search for `BaseSettings` in the project** (grep all .py files). This check is mandatory.

## Pydantic-Settings Fix (CRITICAL)

IF the project has a class that inherits from `BaseSettings` and reads from `.env`:

```python
# ❌ WRONG — app will CRASH with "extra fields not permitted" when it sees NEATLOGS_* vars
class Settings(BaseSettings):
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }

# ✅ RIGHT — "extra": "ignore" allows unknown env vars like NEATLOGS_API_KEY
class Settings(BaseSettings):
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }
```

If `model_config` uses `SettingsConfigDict`, same fix:

```python
# ✅ RIGHT
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )
```

## Why this matters

When you add `NEATLOGS_API_KEY` to `.env`, pydantic-settings will try to load ALL env vars from that file. If the Settings class doesn't have fields for them AND doesn't allow extras, the app crashes on import. This is a guaranteed runtime error.

## Verify BEFORE moving to step 4

1. Run `check_env_keys` tool — confirm `NEATLOGS_API_KEY` exists in `.env`.
2. `.gitignore` contains `.env`.
3. Grep for `BaseSettings` in all .py files. IF found: confirm `"extra": "ignore"` is present in the model_config of that class. If you skipped this, the app WILL crash.
