# Step 6: Decorate Tool Functions

## Action

Scan the project for functions that act as discrete tools/capabilities that the pipeline invokes. Decorate them with `@neatlogs.span(kind="TOOL", tool_name="...", description="...")`.

## CRITICAL: Do NOT Decorate Auto-Instrumented Tools

If `"langchain"` is in the instrumentations list, the following are ALREADY auto-traced as TOOL spans:

- Any function decorated with `@tool` from `langchain_core.tools`
- Any function decorated with `@tool` from `langchain.tools`
- Any class inheriting from `BaseTool`
- Tool calls invoked via `ToolNode` in LangGraph

Similarly for other agent frameworks:
- `"crewai"` → CrewAI `@tool` functions are auto-traced
- `"llamaindex"` → LlamaIndex tool classes are auto-traced
- `"openai_agents"` → OpenAI Agents SDK tools are auto-traced
- `"pydantic_ai"` → PydanticAI tool functions are auto-traced

**Adding `@neatlogs.span(kind="TOOL")` to these creates DUPLICATE spans. Never do it.**

## Decision Gate

For each potential tool function, ask:
1. Does it already have `@tool` from any framework? → **SKIP** (auto-instrumented)
2. Does it inherit from `BaseTool`? → **SKIP** (auto-instrumented)
3. Is it called exclusively within a framework's tool execution? → **SKIP**

Only decorate functions that:
- Perform I/O, external API calls, or significant computation
- Are NOT managed by an auto-instrumented framework
- Are called directly from your own code (not through a framework's tool dispatch)

## What Qualifies as a TOOL (when NOT auto-instrumented)

A function is a TOOL if it:
- Performs a single discrete operation (read file, search, parse, count tokens)
- Has a clear input/output contract
- Is called by orchestration functions as a capability
- Wraps an external service, API, or I/O operation

## Examples

```python
# ✅ RIGHT — standalone tool function, NOT part of any framework
@neatlogs.span(kind="TOOL", tool_name="read_document", description="Read document from disk")
def read_document(file_path: str) -> str:
    with open(file_path, 'r') as f:
        return f.read()

# ✅ RIGHT — external API call, not covered by any instrumentor
@neatlogs.span(kind="TOOL", tool_name="web_search", description="Search the web")
def web_search(query: str) -> list[str]:
    return search_api.search(query)

# ❌ WRONG — this is a LangChain @tool, already auto-instrumented
@neatlogs.span(kind="TOOL", tool_name="query_sales")  # REMOVE THIS
@tool
def query_sales_data(start_date: str, end_date: str) -> str:
    ...

# ❌ WRONG — this is a LangChain @tool, already auto-instrumented
@tool
@neatlogs.span(kind="TOOL", tool_name="calculate")  # REMOVE THIS
def calculate(expression: str) -> str:
    ...
```

## What is NOT a TOOL

- LangChain/CrewAI/LlamaIndex framework-managed tools (auto-instrumented!)
- Pure utility helpers (string formatting, list manipulation)
- Functions with < 3 lines of trivial logic
- Internal helper functions only called by one parent
- Config loaders, logger setup, validation-only functions

## Verification

- Functions that perform I/O, API calls, or significant computation as standalone capabilities have `@span(kind="TOOL")`.
- NO function with `@tool` from `langchain_core.tools` has a neatlogs decorator.
- Each TOOL span has `tool_name` and `description` parameters set.
- Pure utility functions are NOT decorated.
