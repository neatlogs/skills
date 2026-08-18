# Step 5: Optional App-Owned WORKFLOW Span

## Action

The handler self-roots a parentless supported chain/graph call. Add at most one `@neatlogs.span(kind="WORKFLOW")` to the user-facing entry only when that function owns meaningful pre/post work or coordinates multiple calls. A pass-through containing one supported invocation needs no manual root.

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
    # LangGraph: the handler goes on the graph invocation (see step 4).
    result = graph.invoke({"messages": [HumanMessage(content=query)]}, config={"callbacks": [handler]})
    print(result["messages"][-1].content)

# ✅ RIGHT — FastAPI route that invokes the graph
@app.post("/analyze")
@neatlogs.span(kind="WORKFLOW", name="analyze_endpoint")
async def analyze_endpoint(request: AnalyzeRequest):
    validate_request(request)
    result = await graph.ainvoke({"messages": [HumanMessage(content=request.query)]}, config={"callbacks": [handler]})
    await save_run_result(result)
    return {"result": result["messages"][-1].content}
```

## Why At Most One Decorator

The callback handler (Step 4) already creates spans for:
- Every graph node execution
- Every LLM call inside nodes (the graph-invocation handler covers them)
- Every tool call via ToolNode
- Chain / LCEL execution

The handler self-roots, and a graph-level callback already keeps its nodes, LLM calls, tools, and retrievers in one hierarchy. An app-owned outer `WORKFLOW` is useful only when the entry point itself is the operation being measured—for example, it validates input, runs retrieval before the graph, writes the result afterward, or coordinates more than one top-level run.

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
3. If it owns the surrounding orchestration described above, add `@neatlogs.span(kind="WORKFLOW", name="descriptive_name")`; otherwise leave it undecorated
4. Add `import neatlogs` to that file only if the decorator is used

## Verify BEFORE moving to step 6

- At most one function has `@neatlogs.span(kind="WORKFLOW")`; zero is correct for a single supported invocation
- If present, that function is a real user-facing orchestrator (click command, main(), route handler), not a pass-through
- NO graph node functions have any `@neatlogs.span()` or `@neatlogs.trace()` decorator on the `def` line
- NO `@tool` functions have any neatlogs decorator
