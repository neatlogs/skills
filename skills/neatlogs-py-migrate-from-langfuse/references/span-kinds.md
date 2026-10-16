# Span kinds — for the migration

## What to use, when

The `@neatlogs.span()` decorator validates the `kind=` argument
against a fixed set. Picking the right one matters because the
NeatLogs dashboard groups traces by span kind, and downstream
analytics (cost per agent, errors per tool) depend on the kind
being right.

| Kind | When |
|---|---|
| `WORKFLOW` | The user-facing entry. The function a person / CLI / route invokes. One per request. |
| `AGENT` | An autonomous decision loop: reason → act → observe. A Pydantic AI `Agent.run`, an OpenAI Agents `Runner.run`, a CrewAI crew kickoff, a `*_agent` / `run_agent` function with a tool-calling loop. |
| `CHAIN` | Multi-step orchestration that SEQUENCES calls (pre-process → model → post-process) without a tool-calling loop. A `dspy.Module.forward`, a custom `process_*` pipeline. |
| `TOOL` | A discrete capability: one input, one output, one job. The thing an agent CALLS. Use `tool_name=` and `description=`. |
| `RETRIEVER` | RAG fetch: query in, documents out. |
| `EMBEDDING` | Text → vector. |
| `RERANKER` | Re-orders candidate docs by relevance (cohere.rerank, etc.). |
| `GUARDRAIL` | Validates / filters / scores content (PII check, safety classifier). |
| `MCP_TOOL` | MCP protocol tool handlers. |
| `LLM` | A model call. **Not accepted by `@span()`** — create via `neatlogs.trace(kind="LLM")` to attach prompt templates. |
| `VECTOR_STORE` | A vector DB write/query. **Not accepted by `@span()`** — create via `neatlogs.trace()`. |
| `RERANKER` | Same — only via `trace()`. |

## Migration table: Langfuse `@observe(as_type=...)` → NeatLogs kind

This is the heart of step 5. The `as_type` parameter on Langfuse's
`@observe` decorator maps to a NeatLogs kind:

| Langfuse `as_type=` | What it is | NeatLogs |
|---|---|---|
| (not set) / `"span"` | A generic span — function call, sub-step | `@neatlogs.span(kind="CHAIN", name=...)` (the closest default; if it's a tool, use TOOL) |
| `"agent"` | The agent decision loop | `@neatlogs.span(kind="AGENT", name=...)` |
| `"generation"` | An LLM call (chat completion) | `with neatlogs.trace("name", kind="LLM", system_prompt_template=..., user_prompt_template=...)` |
| `"tool"` | A tool the agent calls | `@neatlogs.span(kind="TOOL", tool_name=..., description=...)` |
| `"retriever"` | RAG fetch | `@neatlogs.span(kind="RETRIEVER")` |
| `"embedding"` | Text → vector | `@neatlogs.span(kind="EMBEDDING")` |
| `"evaluator"` | Scoring / grading | `@neatlogs.span(kind="GUARDRAIL")` |
| `"chain"` | Sequential steps | `@neatlogs.span(kind="CHAIN", name=...)` |

Note: Langfuse's `as_type="generation"` is NOT the same as NeatLogs
`kind="LLM"`. In Langfuse, `"generation"` is the kind for a model
call; in NeatLogs, the kind is `"LLM"`. The shape is similar
(model + tokens + prompt + completion) but the API is different
(Langfuse attributes on the current span; NeatLogs uses
`neatlogs.trace("name", kind="LLM", system_prompt_template=...)`
inside the function body).

## How the choice propagates

`@neatlogs.span(kind="AGENT")` on `researcher()` makes that function
the AGENT root. Calls made inside `researcher()` (LLM, tools, other
spans) become children. The dashboard groups by AGENT for
per-agent analytics, by LLM for cost-per-model, by TOOL for
per-tool latency.

If you have a function that does:
```python
@observe()
def pipeline(query):
    user_input = ...
    response = openai_client.chat.completions.create(...)
    return response.choices[0].message.content
```

The NeatLogs equivalent is **NOT** `@neatlogs.span(kind="LLM")` —
that span would lack the surrounding context. It's:
```python
@neatlogs.span(kind="CHAIN", name="pipeline")  # the orchestration
def pipeline(query):
    user_input = ...
    with neatlogs.trace("chat", kind="LLM",
                        system_prompt_template=...,
                        user_prompt_template=...):
        response = openai_client.chat.completions.create(...)
    return response.choices[0].message.content
```

The outer CHAIN holds the user input and the LLM span. The inner
LLM span holds the prompt and tokens. Both are visible in the
dashboard; the cost/analytics split correctly.

## The decorator vs. context manager choice

- `@neatlogs.span(kind=...)` for a whole function (the common case).
  Span attrs (input, output, name) come from the function's args
  and return value.
- `with neatlogs.trace("name", kind=...)` for a block inside a
  function (e.g. just the LLM call, not the surrounding
  orchestration). Span attrs come from `set_attribute()` calls
  inside the block.

If the original `@observe` covered the whole function, use
`@neatlogs.span`. If it covered only a block, use `trace()`.

## Forbidden: don't put a `@span` on top of an already-wrapped call

The NeatLogs trace processor auto-creates a WORKFLOW root for a
wrapped LLM call (e.g. `client = neatlogs.wrap(OpenAI()); client.chat.completions.create(...)`).
Adding `@neatlogs.span(kind="LLM")` on top of that creates
duplicate spans. The pattern is:

- `@neatlogs.span(kind=...)` for YOUR orchestration code only.
- LLM spans on the wrapped call happen automatically; do not add
  another decorator.
- For prompt management: wrap the LLM call with
  `with neatlogs.trace("name", kind="LLM", system_prompt_template=...)`
  INSIDE the orchestration. This adds prompt-template context to
  the auto-LLM-span without creating a new span.
