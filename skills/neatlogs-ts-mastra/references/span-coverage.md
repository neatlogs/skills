# Reference: wrapMastra span coverage

What each wrapped Mastra entity produces, and the canonical `neatlogs.*` attributes captured. All validated end-to-end against `@mastra/core` 1.37.1 with OpenAI, Anthropic, and Google models.

## Span kinds by entity

| Wrapped entity | Method(s) hooked | Span kind | Nesting |
|----------------|------------------|-----------|---------|
| `Agent` | `generate()`, `stream()` | `AGENT` | parent of LLM + TOOL |
| resolved model (auto, via agent) | `doGenerate()`, `doStream()` | `LLM` | child of AGENT, one per model step |
| tool | `execute()` (each tool) | `TOOL` | child of AGENT, one per call |
| `Workflow` | `createRun().start()` / `.resume()` | `WORKFLOW` | parent of step spans |
| `MastraVector` | `query()` | `RETRIEVER` | — |
| `MastraVector` | `upsert()` / `updateVector()` / `deleteVector()` / `createIndex()` / `deleteIndex()` | `VECTOR_STORE` | — |
| `MastraMemory` | `recall()` / `saveMessages()` / `updateWorkingMemory()` / `deleteMessages()` | `CHAIN` | — |
| `MDocument` | `chunk()` | `CHAIN` | — |
| `rerank()` (via `wrapMastraRerank`) | the function call | `RERANKER` | — |
| root `Mastra` | `getAgent`/`getAgentById`/`getWorkflow`/`getWorkflowById` | proxy | wraps returned entities |

## Attributes captured (canonical keys)

**AGENT** — `neatlogs.span.kind`, `neatlogs.agent.name`, `neatlogs.agent.input`, `neatlogs.agent.output`, `neatlogs.llm.model_name`, `neatlogs.llm.system_prompt`, `neatlogs.llm.is_streaming` (stream only).

**LLM** — `neatlogs.llm.model_name`, `neatlogs.llm.provider`, `neatlogs.llm.token_count.{prompt,completion,total}`, `neatlogs.llm.stop_reason`, `neatlogs.llm.invocation_parameters`, `neatlogs.llm.temperature` / `max_tokens` / `top_p` / `top_k` / `frequency_penalty` / `presence_penalty` (when set), `neatlogs.llm.tools.{i}` (advertised tools), `neatlogs.llm.tool_calls.{i}.{id,name,arguments}`, `neatlogs.llm.output_messages.0.{role,content}`, `neatlogs.llm.input`.

**TOOL** — `neatlogs.tool.name`, `neatlogs.tool.description`, `neatlogs.tool.input`, `neatlogs.tool.output`.

**WORKFLOW** — `neatlogs.workflow.name`, `neatlogs.workflow.input`, `neatlogs.workflow.output`, `neatlogs.metadata` (status).

**RETRIEVER / VECTOR_STORE** — `neatlogs.db.system`, `neatlogs.db.operation`, `neatlogs.vectordb.index_name`, `neatlogs.retriever.top_k` (query), `neatlogs.{retriever|vector_store}.input/output`.

**CHAIN (memory / document)** — `neatlogs.db.operation`, `neatlogs.db.documents_count` (chunk), `neatlogs.chain.input/output`.

**RERANKER** — `neatlogs.reranker.query`, `neatlogs.reranker.input_documents`, `neatlogs.reranker.output_documents`, `neatlogs.reranker.top_k`.

## Streaming

`agent.stream()` returns a `MastraModelOutput` (not a plain async-iterable). wrapMastra keeps the AGENT span open across the whole stream: the model's `doStream` nests as an LLM child, and the final output/usage/stop-reason are recorded when the stream completes — whether the caller drains `.textStream`/`.fullStream` or awaits `.text`. No code change needed on the consumer side.

## Example tree (single agent run with a tool)

```
AGENT  mastra.agent.Project Manager
 ├─ LLM   mastra.llm.gpt-4o-mini.doGenerate   (decides to call a tool)
 ├─ TOOL  mastra.tool.search-tickets           (executed by the runtime)
 └─ LLM   mastra.llm.gpt-4o-mini.doGenerate   (final answer)
```

Note: tools are siblings of the LLM steps under the AGENT orchestrator — NOT children of an LLM span. The LLM *requests* a tool, then returns; the runtime executes the tool after that LLM call has ended, so the orchestrator (AGENT) is the correct parent.
