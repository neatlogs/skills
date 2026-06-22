# Step 2: Add neatlogs.init() BEFORE importing run_agent

1. Find the entry point.
2. Add `import os`, `import neatlogs`; `load_dotenv()` before init.
3. Call `init()` with `instrumentations=["hermes", "openai"]` BEFORE
   `from run_agent import AIAgent`.

```python
import os
import neatlogs
from dotenv import load_dotenv

load_dotenv()
neatlogs.init(
    api_key=os.getenv("NEATLOGS_API_KEY"),
    workflow_name="my-hermes-app",
    # hermes → AGENT/TOOL spans; openai → the LLM spans (Hermes calls OpenAI/OpenRouter).
    instrumentations=["hermes", "openai"],
)

from run_agent import AIAgent   # MUST come AFTER init()
```

## CRITICAL ORDERING
The `hermes` instrumentor patches `AIAgent.run_conversation` and
`ToolRegistry.dispatch` at import time. If `from run_agent import AIAgent` runs
BEFORE `init()`, the patch is missed and no AGENT/TOOL spans are produced. Always
init first, import Hermes second.

## NOTE
If the app uses a non-OpenAI Hermes provider adapter (anthropic / bedrock /
gemini / codex), add that provider to the list, e.g.
`instrumentations=["hermes", "anthropic"]`.
