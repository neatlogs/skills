# Step 2: Add neatlogs.init()

1. Find the entry point.
2. Add `import os`, `import neatlogs`; `load_dotenv()` before init.
3. Call `init()` BEFORE importing `agno`.

```python
import os
import neatlogs
from dotenv import load_dotenv

load_dotenv()
neatlogs.init(api_key=os.getenv("NEATLOGS_API_KEY"), workflow_name="my-agno-app")

from agno.agent import Agent   # after init
```

## NOTE
No `instrumentations=[...]` needed — `neatlogs.wrap()` installs the hooks. Add a provider entry only if the app ALSO calls a provider SDK directly outside Agno.
