# Step 2: Add neatlogs.init()

1. Find the entry point.
2. Add `import os`, `import neatlogs`; `load_dotenv()` before init.
3. Call `init()` BEFORE importing `strands` — the global tracer provider must exist before Strands reads it, or its native spans won't be exported.

```python
import os
import neatlogs
from dotenv import load_dotenv

load_dotenv()
neatlogs.init(api_key=os.getenv("NEATLOGS_API_KEY"), workflow_name="my-strands-app")

from strands import Agent   # after init
```

## NOTE
No `instrumentations=[...]` needed — init() + Strands' native OTel captures AGENT/LLM/TOOL spans. You DO wrap each agent with `neatlogs.strands_hooks(agent)` (Step 4) to capture input/output content; without it spans show tokens but empty I/O.
