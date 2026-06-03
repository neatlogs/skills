# Step 2: Add neatlogs.init()

1. Find the entry point.
2. Add `import os`, `import neatlogs`; call `load_dotenv()` (if used) before init.
3. Call `init()` BEFORE importing `dspy` — its class-level hooks must patch before DSPy classes are used.

```python
import os
import neatlogs
from dotenv import load_dotenv

load_dotenv()
neatlogs.init(api_key=os.getenv("NEATLOGS_API_KEY"), workflow_name="my-dspy-app")

import dspy   # after init
```

## NOTE
No `instrumentations=[...]` needed — `neatlogs.wrap()` installs the DSPy hooks. Add a provider entry only if the app ALSO calls a provider SDK directly outside DSPy.
