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
| `RERANKER` | Re-orders candidate docs by relevance. **Not accepted by `@span()`** — create via `neatlogs.trace()`. |
| `GUARDRAIL` | Validates / filters / scores content. |
| `EVALUATOR` | A custom evaluator function that scores output quality (answer vs reference, criteria rubric, LLM-as-judge step). Accepted by `@span()`. |
| `MEMORY` | Memory save / recall operations against a memory store. Accepted by `@span()`. |
| `MCP_TOOL` | MCP protocol tool handlers. |
| `LLM` | A model call. **Not accepted by `@span()`** — create via `neatlogs.trace(kind="LLM")` to attach prompt templates. |
| `VECTOR_STORE` | A vector DB write or index management; vector search is a RETRIEVER. **Not accepted by `@span()`** — create via `neatlogs.trace()`. |

## Migration table: LangSmith `@traceable(run_type=...)` → NeatLogs kind

This is the heart of step 5. The `run_type` parameter on
LangSmith's `@traceable` decorator maps to a NeatLogs kind.
(The LangSmith docs document the full enum; below covers the
common cases.)

| LangSmith `run_type=` | What it is | NeatLogs |
|---|---|---|
| (not set) | A generic traceable — function call, sub-step | `@neatlogs.span(kind="CHAIN", name=...)` (the closest default; if it's a tool, use TOOL) |
| `"llm"` | An LLM call (chat completion) | `with neatlogs.trace("name", kind="LLM", system_prompt_template=..., user_prompt_template=...)` |
| `"tool"` | A tool the agent calls | `@neatlogs.span(kind="TOOL", tool_name=..., description=...)` |
| `"chain"` | Sequential steps | `@neatlogs.span(kind="CHAIN", name=...)` |
| `"agent"` | The agent decision loop | `@neatlogs.span(kind="AGENT", name=...)` |
| `"retriever"` | RAG fetch | `@neatlogs.span(kind="RETRIEVER")` |
| `"embedding"` | Text → vector | `@neatlogs.span(kind="EMBEDDING")` |
| `"parser"` | Output parser | `@neatlogs.span(kind="CHAIN", name=...)` (parsers are typically just CHAIN; LLM is on the model call that produced the parsed text) |
| `"prompt"` | Prompt template render | (don't wrap — prompt templates are pure; the LLM call that uses them is what gets the LLM span) |

Note: LangSmith's `run_type="llm"` is NOT the same as NeatLogs
`kind="LLM"`. The shape is similar (model + tokens + prompt +
completion) but the API is different (LangSmith sets
attributes on the current span; NeatLogs uses
`neatlogs.trace("name", kind="LLM", system_prompt_template=...)`
inside the function body).

## How the choice propagates

`@neatlogs.span(kind="AGENT")` on `researcher()` makes that
function the AGENT root. Calls made inside `researcher()` (LLM,
tools, other spans) become children. The dashboard groups by
AGENT for per-agent analytics, by LLM for cost-per-model, by
TOOL for per-tool latency.

If you have a function that does:
```python
@traceable()
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

- `@neatlogs.span(kind=...)` for a whole function (the common
  case). Span attrs (input, output, name) come from the
  function's args and return value.
- `with neatlogs.trace("name", kind=...)` for a block inside a
  function (e.g. just the LLM call, not the surrounding
  orchestration). Span attrs come from `set_attribute()` calls
  inside the block.

If the original `@traceable` covered the whole function, use
`@neatlogs.span`. If it covered only a block, use `trace()`.

## Forbidden: don't put a `@span` on top of an already-wrapped call

The NeatLogs trace processor auto-creates a WORKFLOW root for
a wrapped LLM call (e.g. `client = neatlogs.wrap(OpenAI());
client.chat.completions.create(...)`). Adding
`@neatlogs.span(kind="LLM")` on top of that creates duplicate
spans. The pattern is:

- `@neatlogs.span(kind=...)` for YOUR orchestration code only.
- LLM spans on the wrapped call happen automatically; do not
  add another decorator.
- For prompt management: wrap the LLM call with
  `with neatlogs.trace("name", kind="LLM",
  system_prompt_template=...)` INSIDE the orchestration. This
  adds prompt-template context to the auto-LLM-span without
  creating a new span.

## LangChain-specific note

If the project uses LangChain, the `langchain.observability`
callback (v0.3+) or the `langchain.tracing` context manager
(v0.2) auto-wraps chains, agents, tools, and retrievers with
the right kinds. After step 4 re-points the OTel endpoint to
NeatLogs, the LangChain spans flow through to NeatLogs with the
correct kinds assigned by LangChain (and mapped to NeatLogs'
`kind=` taxonomy by the NeatLogs LangChain handler).

You should NOT replace `langchain.observability` callback
spans with `@neatlogs.span` decorators unless the project is
using a non-standard LangChain surface (e.g. a custom
`Runnable` that doesn't go through the callback). For the
common case, leave the callback in place and let the OTel route
do the work.
