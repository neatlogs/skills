# Step 2: Add neatlogs.init() BEFORE importing run_agent

1. Find the entry point.
2. Add `import os`, `import neatlogs`; `load_dotenv()` before init.
3. Call `init()` with `instrumentations=["hermes"]` BEFORE
   `from run_agent import AIAgent`.

```python
import os
import neatlogs
from dotenv import load_dotenv

load_dotenv()
neatlogs.init(
    api_key=os.getenv("NEATLOGS_API_KEY"),
    workflow_name="my-hermes-app",
    # "hermes" → AGENT (run_conversation) + TOOL spans. It AUTO-LOADS "openai" for
    # the LLM spans, because Hermes' default mode calls the openai SDK (OpenRouter).
    # So just "hermes" is enough — no need to list "openai" yourself.
    instrumentations=["hermes"],
)

from run_agent import AIAgent   # MUST come AFTER init()
```

## CRITICAL ORDERING
The `hermes` instrumentor patches `AIAgent.run_conversation` and
`ToolRegistry.dispatch` at import time. If `from run_agent import AIAgent` runs
BEFORE `init()`, the patch is missed and no AGENT/TOOL spans are produced. Always
init first, import Hermes second.

## NOTE — non-OpenAI Hermes providers
Hermes can route through a non-OpenAI adapter at runtime (`anthropic_messages`,
`bedrock_converse`, gemini) instead of the default OpenAI/OpenRouter mode. Those
calls go through a DIFFERENT SDK, which "hermes" auto-load (openai) won't cover —
so the LLM span would be missed. If the app is configured for one of those, add
that provider explicitly, e.g. `instrumentations=["hermes", "anthropic"]`
(or `bedrock` / `google_genai`). Stick with just `["hermes"]` for the default
OpenAI/OpenRouter setup.
