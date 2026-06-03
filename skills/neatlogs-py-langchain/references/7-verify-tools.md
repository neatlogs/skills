# Step 7: Verify Tool Functions Are Untouched

## Action

Confirm that NO `@tool`-decorated function has a neatlogs decorator. This step is a verification pass, not an action step.

## Why This Step Exists

The callback handler automatically traces ALL `@tool` functions invoked through ToolNode from `langchain_core.tools`. Adding `@neatlogs.span()` or `@neatlogs.trace()` creates duplicate spans that pollute the trace view.

## What to Check

Search the project for all files containing `@tool`. For each one, verify:

1. There is NO `@neatlogs.span(...)` above or below `@tool`
2. There is NO `@neatlogs.trace(...)` inside the function body
3. There is NO `with neatlogs.trace(...)` wrapping the function's logic

## If You Find a Violation — Remove It

```python
# ❌ FOUND THIS — remove the neatlogs decorator
@neatlogs.span(kind="TOOL", tool_name="query_sales")
@tool
def query_sales_data(start_date: str, end_date: str) -> str:
    """Query sales data for the given date range."""
    ...

# ✅ SHOULD BE THIS — just @tool, nothing else
@tool
def query_sales_data(start_date: str, end_date: str) -> str:
    """Query sales data for the given date range."""
    ...
```

```python
# ❌ FOUND THIS — remove the trace() wrapper
@tool
def calculate(expression: str) -> str:
    """Evaluate a math expression."""
    with neatlogs.trace("calculate", kind="TOOL"):  # REMOVE
        return str(eval(expression))

# ✅ SHOULD BE THIS — no trace wrapper
@tool
def calculate(expression: str) -> str:
    """Evaluate a math expression."""
    return str(eval(expression))
```

## What About Non-Framework Tool Functions?

If the project has standalone tool-like functions (not decorated with `@tool`) that perform I/O or external API calls and are NOT called through LangChain's ToolNode:

- These CAN get `@neatlogs.span(kind="TOOL", tool_name="...", description="...")`
- But this is rare in LangChain projects — most tools go through the framework

## Verification

- [ ] Grep for `@tool` in all Python files
- [ ] None of those functions have any neatlogs decorator
- [ ] None of those functions have `with neatlogs.trace(...)` inside them
- [ ] If you added any neatlogs decorators to @tool functions in earlier steps by mistake, remove them now
