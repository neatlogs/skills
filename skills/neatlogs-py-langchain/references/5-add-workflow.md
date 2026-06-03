# Step 5: Add WORKFLOW Span to User-Facing Entry Point

## Action

Find the ONE function that the user calls to start the LangGraph/LangChain workflow. That function — and ONLY that function — gets `@neatlogs.span(kind="WORKFLOW")`.

## How to Find It

The WORKFLOW function is the one that:
- Calls `graph.invoke(...)` or `graph.ainvoke(...)` or `app.invoke(...)` or `app.ainvoke(...)`
- OR calls `chain.invoke(...)` / `chain.ainvoke(...)`
- AND is directly triggered by the user (CLI command, HTTP endpoint, main() function)

## WRONG vs RIGHT

```python
# ❌ WRONG — graph node functions are NOT workflows. The handler traces them.
@neatlogs.span(kind="WORKFLOW")
def analyst_node(state: AgentState) -> dict:
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}

# ❌ WRONG — graph node functions should NOT get any @span decorator
@neatlogs.span(kind="CHAIN")
def planner_node(state: AgentState) -> dict:
    response = llm.invoke(messages)
    return {"messages": [response]}

# ❌ WRONG — internal helper that calls graph.invoke is NOT the user-facing entry
@neatlogs.span(kind="WORKFLOW")
def run_analysis(query: str):
    return graph.invoke({"messages": [HumanMessage(content=query)]})

# ✅ RIGHT — the CLI command / route handler that the user directly triggers
@cli.command()
@click.argument("query")
@neatlogs.span(kind="WORKFLOW", name="analytics_agent")
def analyze(query: str):
    result = run_analysis(query)
    print(result)

# ✅ RIGHT — main() if that's what runs the graph
@neatlogs.span(kind="WORKFLOW", name="analytics_agent")
def main():
    query = input("Enter your question: ")
    result = graph.invoke({"messages": [HumanMessage(content=query)]})
    print(result["messages"][-1].content)

# ✅ RIGHT — FastAPI route that invokes the graph
@app.post("/analyze")
@neatlogs.span(kind="WORKFLOW", name="analyze_endpoint")
async def analyze_endpoint(request: AnalyzeRequest):
    result = await graph.ainvoke({"messages": [HumanMessage(content=request.query)]})
    return {"result": result["messages"][-1].content}
```

## Why Only ONE Decorator

The callback handler (Step 4) already creates spans for:
- Every graph node execution
- Every LLM call inside nodes (where the handler is attached)
- Every tool call via ToolNode
- Chain / LCEL execution

You only need ONE `@span(kind="WORKFLOW")` at the top to:
1. Create the trace root (the handler's spans inherit this trace ID)
2. Mark the beginning and end of the user-facing operation

## Do NOT Decorate These

| Function type | Why NOT |
|--------------|---------|
| Graph node functions (planner_node, analyst_node) | Traced by the callback handler |
| `@tool`-decorated functions | Auto-traced as TOOL spans |
| Internal helpers (run_analysis, build_graph) | Not meaningful trace boundaries |
| Graph construction (create_graph, add_nodes) | Build-time, not runtime |

## Action Steps

1. Find where `graph.invoke()` / `graph.ainvoke()` / `app.invoke()` is called
2. Trace UP to the user-facing function that initiates this call
3. Add `@neatlogs.span(kind="WORKFLOW", name="descriptive_name")` to that function
4. Add `import neatlogs` to that file if not present
5. That's it. ONE decorator total.

## Verify BEFORE moving to step 6

- Exactly ONE function has `@neatlogs.span(kind="WORKFLOW")`
- That function is the user-facing entry point (click command, main(), route handler)
- NO graph node functions have any `@neatlogs.span()` or `@neatlogs.trace()` decorator on the `def` line
- NO `@tool` functions have any neatlogs decorator
