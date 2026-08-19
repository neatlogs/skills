# Span Kinds Reference

Supported wrappers, handlers, hooks, processors, and native integrations own the semantic spans they capture. The manual non-root examples below are only for unsupported/raw/custom operations and assume the real application path already has an active parentless `WORKFLOW`, `CHAIN`, `AGENT`, or `MCP_TOOL` root. Do not add a placeholder root around a lone supported call; supported capture layers self-root. `@span()` accepts `EVALUATOR` and `MEMORY`; only `LLM`, `RERANKER`, and `VECTOR_STORE` are rejected.

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
    for i, document in enumerate(results):
        span.set_attribute(f"neatlogs.retriever.documents.{i}", json.dumps(document))
    span.set_attribute("neatlogs.retriever.output", json.dumps(results))
```

## RERANKER
Query + candidate documents → reordered docs/scores (cohere.rerank, bge-reranker, `invoke_model` on a *rerank* model). NOT an LLM — use RERANKER even over raw HTTP / Bedrock `invoke_model`.
```python
with neatlogs.trace("rerank", kind="RERANKER") as span:
    span.set_attribute("neatlogs.reranker.model_name", model)
    span.set_attribute("neatlogs.reranker.query", query)
    span.set_attribute("neatlogs.reranker.top_k", top_n)
    for i, document in enumerate(documents):
        span.set_attribute(f"neatlogs.reranker.input_documents.{i}", json.dumps(document))
    reranked = do_rerank(query, documents, top_n)           # the existing call
    for i, document in enumerate(reranked):
        span.set_attribute(f"neatlogs.reranker.output_documents.{i}", json.dumps(document))
    span.set_attribute("neatlogs.reranker.output", json.dumps(reranked))
```

## VECTOR_STORE
Use for vector-database writes and index management; vector search is a RETRIEVER.
```python
with neatlogs.trace("upsert_documents", kind="VECTOR_STORE") as span:
    span.set_attribute("neatlogs.db.system", "custom_vector_db")
    span.set_attribute("neatlogs.db.operation", "upsert")
    span.set_attribute("neatlogs.db.collection_name", collection_name)
    span.set_attribute("neatlogs.vectordb.index_name", index_name)
    span.set_attribute("neatlogs.vector_store.input", json.dumps(documents))
    result = store.upsert(documents)
    span.set_attribute("neatlogs.vector_store.output", json.dumps(result))
```

## EMBEDDING
Text → vector (`.embeddings.create`, `embed_documents`, titan-embed, `invoke_model` on an *embed* model). Use EMBEDDING even over raw HTTP / Bedrock — NOT LLM.
```python
@neatlogs.span(kind="EMBEDDING")
def embed_texts(texts): ...
```
Raw-API form (set canonical attributes by hand; record the vector only when its size and data policy permit):
```python
with neatlogs.trace("embed", kind="EMBEDDING") as span:
    span.set_attribute("neatlogs.embedding.model_name", model)
    span.set_attribute("neatlogs.embedding.text", text)
    vector = do_embed(text)                                 # the existing call
    span.set_attribute("neatlogs.embedding.token_count", token_count)
    span.set_attribute("neatlogs.embedding.vector", vector)
    span.set_attribute("neatlogs.embedding.output", json.dumps({"dimensions": len(vector)}))
```

## GUARDRAIL
Validates / filters / scores / sanitizes content (PII check, safety filter, output validator, moderation, a classifier scoring a span).
```python
with neatlogs.trace("safety_check", kind="GUARDRAIL") as span:
    span.set_attribute("neatlogs.guardrail.input", text)
    passed = run_check(text)                                # the existing call
    span.set_attribute("neatlogs.guardrail.passed", passed)
    span.set_attribute("neatlogs.guardrail.output", json.dumps({"passed": passed}))
```

## EVALUATOR
```python
@neatlogs.span(kind="EVALUATOR", name="answer_quality")
def evaluate_answer(answer, reference):
    return {"score": evaluate(answer, reference)}
```
Use `@span` for an ordinary custom evaluator function so function input/output and errors are captured automatically. Use `trace(kind="EVALUATOR")` only when there is no decorator boundary or direct canonical metadata is required, such as a DeepEval lifecycle callback. That trace is the sole owner; never combine it with `@span` for the same evaluation.

## MEMORY
```python
@neatlogs.span(kind="MEMORY", name="save_memory")
def save_memory(user_id, fact):
    return memory_store.save(user_id, fact)
```

> **Exact attribute keys:** LLM uses `neatlogs.llm.provider`, `neatlogs.llm.model_name`, `neatlogs.llm.input_messages.{i}.role`, `neatlogs.llm.input_messages.{i}.content`, `neatlogs.llm.output_messages.{i}.role`, `neatlogs.llm.output_messages.{i}.content`, `neatlogs.llm.token_count.prompt`, `neatlogs.llm.token_count.completion`, `neatlogs.llm.token_count.total`, and the reported `neatlogs.llm.finish_reason`/`neatlogs.llm.stop_reason`. Retriever uses `neatlogs.retriever.query`, `neatlogs.retriever.top_k`, `neatlogs.retriever.documents.{i}`, `neatlogs.retriever.input`, and `neatlogs.retriever.output`. Reranker uses `neatlogs.reranker.model_name`, `neatlogs.reranker.query`, `neatlogs.reranker.top_k`, `neatlogs.reranker.input_documents.{i}`, `neatlogs.reranker.output_documents.{i}`, `neatlogs.reranker.input`, and `neatlogs.reranker.output`. Vector DB uses `neatlogs.db.system`, `neatlogs.db.operation`, `neatlogs.db.collection_name`, `neatlogs.vectordb.index_name`, `neatlogs.vectordb.embedding_model`, `neatlogs.vectordb.vector_dimension`, `neatlogs.vectordb.similarity_algorithm`, `neatlogs.vector_store.input`, and `neatlogs.vector_store.output`. Embedding uses `neatlogs.embedding.model_name`, `neatlogs.embedding.text`, `neatlogs.embedding.token_count`, `neatlogs.embedding.vector`, `neatlogs.embedding.invocation_parameters`, `neatlogs.embedding.input`, and `neatlogs.embedding.output`. Guardrail uses `neatlogs.guardrail.input`, `neatlogs.guardrail.output`, `neatlogs.guardrail.passed`, and `neatlogs.guardrail.score`. Evaluator uses `neatlogs.evaluator.input`/`neatlogs.evaluator.output` plus JSON `neatlogs.metadata` for its name, criteria, and score. Only set these by hand for raw/custom operations; a wrapper, handler, hook, processor, native integration, or provider instrumentor owns supported calls.

## MCP_TOOL
MCP protocol tool handlers.
```python
@neatlogs.span(kind="MCP_TOOL", tool_name="get_weather")
async def get_weather(location): ...
```
