# Step 5: Trace custom code

Wrap meaningful blocks of your own orchestration code (handlers, tools, pipeline stages) in a span with
`neatlogs.Trace` (a `workflow` root) or `neatlogs.StartSpan` (an explicitly-typed
span at a boundary). Both return a **new ctx**, the span, and an `end` func.

Do not use these APIs to create another LLM span around a `WrapGenAI` call or a
call already owned by `StartLLMSpan`. Add an orchestration span only for an
app-owned request handler, agent loop, or pipeline stage with its own meaningful
pre/post work or multiple children; each child operation still has exactly one
capture owner.

```go
ctx, span, end := neatlogs.Trace(ctx, "handle_request") // workflow root
defer end()
_ = span

// Or a typed child span (kind = "tool", "chain", "agent", …):
ctx, toolSpan, endTool := neatlogs.StartSpan(ctx, "lookup_account", "tool")
defer endTool()
_ = toolSpan
```

## Boundary helpers

Two helpers cover common non-LLM boundaries (both auto-root and use the private
provider):

- **`neatlogs.StartRetrieverSpan(ctx, name, query, topK)`** → `(ctx, *RetrieverSpan)` — any custom retrieval operation that returns context for generation (vector, keyword, hybrid, or application-specific lookup). Call `r.SetDocuments(docs, len(docs))` then `r.End()`; call `r.SetError(err)` on failure. An empty result set is recorded as `"[]"`, never omitted.
- **`neatlogs.StartToolSpanFromHeaders(ctx, headers, toolName, input, neatlogs.IdentifyOptions{})`** → `(ctx, *ToolSpan)` — continue an inbound trace from request headers and open a `tool` span. Call `t.SetOutput(out)` then `t.End()`.

## Unsupported/custom semantic operations

`StartLLMSpan` and `StartRetrieverSpan` populate their canonical fields. For a
custom operation without a helper, use `StartSpan` once and set the applicable
attributes directly with `attribute.String`/`Int`/`Bool`. A parentless custom
`llm`, `tool`, `retriever`, `reranker`, `embedding`, `vector_store`,
`guardrail`, or `evaluator` span cannot finalize by itself; place it below a
real parentless `workflow`, `chain`, `agent`, or `mcp_tool` span. Do not add
that root around a lone supported `WrapGenAI`/helper call because those paths
self-root.

| Kind | Exact canonical attributes |
|---|---|
| `llm` | `neatlogs.llm.provider`, `neatlogs.llm.model_name`, `neatlogs.llm.input_messages.{i}.role`, `neatlogs.llm.input_messages.{i}.content`, `neatlogs.llm.output_messages.{i}.role`, `neatlogs.llm.output_messages.{i}.content`, `neatlogs.llm.token_count.prompt`, `neatlogs.llm.token_count.completion`, `neatlogs.llm.token_count.total`; when reported, `neatlogs.llm.system`, `neatlogs.llm.finish_reason`/`neatlogs.llm.stop_reason`, `neatlogs.llm.is_streaming`, `neatlogs.llm.temperature`, `neatlogs.llm.top_p`, `neatlogs.llm.top_k`, `neatlogs.llm.max_tokens`, `neatlogs.llm.invocation_parameters` |
| `retriever` | `neatlogs.retriever.query`, `neatlogs.retriever.top_k`, `neatlogs.retriever.documents.{i}`, `neatlogs.retriever.input`, `neatlogs.retriever.output` |
| `reranker` | `neatlogs.reranker.model_name`, `neatlogs.reranker.query`, `neatlogs.reranker.top_k`, `neatlogs.reranker.input_documents.{i}`, `neatlogs.reranker.output_documents.{i}`, `neatlogs.reranker.input`, `neatlogs.reranker.output` |
| `vector_store` | `neatlogs.db.system`, `neatlogs.db.operation`, `neatlogs.db.collection_name`, `neatlogs.vectordb.index_name`, `neatlogs.vectordb.embedding_model`, `neatlogs.vectordb.vector_dimension`, `neatlogs.vectordb.similarity_algorithm`, `neatlogs.vector_store.input`, `neatlogs.vector_store.output` |
| `embedding` | `neatlogs.embedding.model_name`, `neatlogs.embedding.text`, `neatlogs.embedding.token_count`, `neatlogs.embedding.vector`, `neatlogs.embedding.invocation_parameters`, `neatlogs.embedding.input`, `neatlogs.embedding.output` |
| `guardrail` | `neatlogs.guardrail.input`, `neatlogs.guardrail.output`, `neatlogs.guardrail.passed`, `neatlogs.guardrail.score` |
| `evaluator` | `neatlogs.evaluator.input`, `neatlogs.evaluator.output`; encode evaluator name, criteria, and score as JSON in `neatlogs.metadata` until dedicated evaluator fields exist |

Use indexed document keys. Do not emit the legacy `neatlogs.retrieval.*`
namespace or invented keys such as `neatlogs.vector_store.query`.

## The rules

- `defer end()` immediately — it closes the span when the function returns.
- Use `Trace` / `StartSpan` for meaningful app-owned orchestration or boundaries,
  not as an extra wrapper around a single automatically captured model call.
- **Pass the returned `ctx` to children.** Nesting is by context: a `Trace` (or a
  `WrapGenAI` / `StartLLMSpan` call) that receives this `ctx` becomes a **child**
  of this span. Reuse the old ctx instead and the child ends up detached.

## Nested example

```go
func handleRequest(ctx context.Context, gc *nlgenai.GenAIModels, req Request) error {
    ctx, _, end := neatlogs.Trace(ctx, "handle_request") // root for this request
    defer end()

    // child span — receives the request ctx, so it nests under handle_request
    parsed, err := parseInput(ctx, req)
    if err != nil {
        return err
    }

    // LLM call under the same ctx → also a child of handle_request
    _, err = gc.GenerateContent(ctx, "gemini-2.5-flash", parsed.Contents, parsed.Cfg)
    return err
}

func parseInput(ctx context.Context, req Request) (Parsed, error) {
    ctx, _, end := neatlogs.Trace(ctx, "parse_input")
    defer end()
    // ... use ctx for anything deeper ...
    return doParse(ctx, req)
}
```

## WRONG vs RIGHT

```go
// ❌ WRONG — ignoring the returned ctx. Children use the old ctx and don't nest.
_, _, end := neatlogs.Trace(ctx, "handle_request")
defer end()
parseInput(ctx, req) // still the OUTER ctx → parse_input is not a child
```

```go
// ✅ RIGHT — thread the returned ctx into every child call.
ctx, _, end := neatlogs.Trace(ctx, "handle_request")
defer end()
parseInput(ctx, req) // nests correctly
```

## Verify

Every `neatlogs.Trace` / `StartSpan` is followed by `defer end()`, and the ctx it
returns is the one handed to any nested `Trace` / `StartLLMSpan` / `WrapGenAI` call.
