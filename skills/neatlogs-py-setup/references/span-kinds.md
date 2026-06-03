# Span Kinds Reference

## WORKFLOW
Top-level entry that orchestrates the full pipeline. One per program/request.
```python
@neatlogs.span(kind="WORKFLOW")
def run_pipeline(input): ...
```

## AGENT
Autonomously DECIDES + ACTS: a reason→act loop (`while True:` / iterate-until-done), a tool-calling/ReAct loop, or a framework agent (pydantic-ai `Agent.run`, openai-agents `Runner.run`, a langgraph graph, an agno agent, a `*_agent`/`run_agent` function that picks tools). Use AGENT — do NOT default an agent loop to WORKFLOW (WORKFLOW is only the outer entry point) and do NOT default it to LLM (the LLM span goes on the model call inside the loop).
```python
@neatlogs.span(kind="AGENT", name="researcher", role="Research Analyst", goal="Find papers")
def researcher(topic): ...   # the loop that decides which tool to call next
```

## CHAIN
Multi-step orchestration that SEQUENCES calls (pre-process → model → post-process), or a framework module/pipeline that is NOT itself the model call (dspy `Module.forward`, a custom pipeline, a `*_chain`/`process_*` function). Use CHAIN, NOT LLM — the LLM span belongs on the actual model call inside; the wrapper is CHAIN.
```python
@neatlogs.span(kind="CHAIN")
async def summarize_and_format(text, settings): ...
```

## TOOL
Discrete capability. Does ONE thing with clear input/output.
```python
@neatlogs.span(kind="TOOL", tool_name="web_search", description="Search the web")
def web_search(query): ...
```

## RETRIEVER
Fetches context for LLM consumption. Query in, documents out (vector/hybrid search, RAG fetch, `.similarity_search`, a search endpoint returning candidate docs).
```python
@neatlogs.span(kind="RETRIEVER")
def retrieve_docs(query, top_k=5): ...
```
When the call is a raw API / custom store auto-instrumentation can't see, set the kind-specific attrs so the span carries data (note the key is `neatlogs.retriever.*`, singular):
```python
with neatlogs.trace("vector_search", kind="RETRIEVER") as span:
    span.set_attribute("neatlogs.retriever.query", query)
    span.set_attribute("neatlogs.retriever.top_k", top_k)
    results = do_search(query, top_k)                       # the existing call
    span.set_attribute("neatlogs.retriever.documents", json.dumps(results))
```

## RERANKER
Query + candidate documents → reordered docs/scores (cohere.rerank, bge-reranker, `invoke_model` on a *rerank* model). NOT an LLM — use RERANKER even over raw HTTP / Bedrock `invoke_model`.
```python
with neatlogs.trace("rerank", kind="RERANKER") as span:
    span.set_attribute("neatlogs.reranker.model_name", model)
    span.set_attribute("neatlogs.reranker.query", query)
    span.set_attribute("neatlogs.reranker.top_k", top_n)
    span.set_attribute("neatlogs.reranker.input_documents", json.dumps(documents))
    reranked = do_rerank(query, documents, top_n)           # the existing call
    span.set_attribute("neatlogs.reranker.output_documents", json.dumps(reranked))
```

## EMBEDDING
Text → vector (`.embeddings.create`, `embed_documents`, titan-embed, `invoke_model` on an *embed* model). Use EMBEDDING even over raw HTTP / Bedrock — NOT LLM.
```python
@neatlogs.span(kind="EMBEDDING")
def embed_texts(texts): ...
```
Raw-API form (set attrs by hand — canonical keys: `text` is the input, `token_count`, `model_name`; the SDK strips the raw vector from the trace view, so don't bother serializing it):
```python
with neatlogs.trace("embed", kind="EMBEDDING") as span:
    span.set_attribute("neatlogs.embedding.model_name", model)
    span.set_attribute("neatlogs.embedding.text", text)
    vector = do_embed(text)                                 # the existing call
    span.set_attribute("neatlogs.embedding.token_count", token_count)
```

## GUARDRAIL
Validates / filters / scores / sanitizes content (PII check, safety filter, output validator, moderation, a classifier scoring a span).
```python
with neatlogs.trace("safety_check", kind="GUARDRAIL") as span:
    span.set_attribute("neatlogs.guardrail.name", "safety")
    span.set_attribute("neatlogs.guardrail.input", text)
    passed = run_check(text)                                # the existing call
    span.set_attribute("neatlogs.guardrail.passed", passed)
    span.set_attribute("neatlogs.guardrail.triggered", not passed)
```

> **Attribute keys:** any attribute you set whose name starts with `neatlogs.` is passed through to the backend verbatim — so the `neatlogs.<kind>.*` keys above land as-is. The canonical/mapped names live in the SDK's `neatlogs/config/attribute-mapping.json`: `neatlogs.retriever.*` (singular — `query`/`top_k`/`documents`), `neatlogs.reranker.*` (`model_name`/`query`/`top_k`/`input_documents`/`output_documents`), `neatlogs.embedding.*` (`model_name`/`text`/`token_count`/`vector` — the raw vector is stripped from the trace view), `neatlogs.llm.*`. (GUARDRAIL has no dedicated mapped keys yet; the `neatlogs.guardrail.*` keys still pass through.) Only set these by hand for raw-HTTP / `invoke_model` / custom calls — a wrapped SDK client or framework handler captures them automatically (don't double-instrument).

## MCP_TOOL
MCP protocol tool handlers.
```python
@neatlogs.span(kind="MCP_TOOL", tool_name="get_weather")
async def get_weather(location): ...
```
