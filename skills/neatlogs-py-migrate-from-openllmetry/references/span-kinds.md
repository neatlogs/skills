# Span kinds — for the migration

## What to use, when

The `@neatlogs.span()` decorator validates the `kind=`
argument against a fixed set. Picking the right one matters
because the NeatLogs dashboard groups traces by span kind,
and downstream analytics (cost per agent, errors per tool)
depend on the kind being right.

| Kind | When |
|---|---|
| `WORKFLOW` | The user-facing entry. The function a person / CLI / route invokes. One per request. |
| `AGENT` | An autonomous decision loop: reason → act → observe. A Pydantic AI `Agent.run`, an OpenAI Agents `Runner.run`, a CrewAI crew kickoff, a `*_agent` / `run_agent` function with a tool-calling loop. |
| `CHAIN` | Multi-step orchestration that SEQUENCES calls (pre-process → model → post-process) without a tool-calling loop. A `dspy.Module.forward`, a custom `process_*` pipeline. |
| `TOOL` | A discrete capability: one input, one output, one job. The thing an agent CALLS. Use `tool_name=` and `description=`. |
| `RETRIEVER` | RAG fetch: query in, documents out. |
| `EMBEDDING` | Text → vector. |
| `RERANKER` | Re-orders candidate docs by relevance. **Trace-only** — create via `neatlogs.trace()`; not accepted by `@span()`. |
| `GUARDRAIL` | Validates / filters / scores content. |
| `EVALUATOR` | An evaluation run (scoring, grading, comparison). Use for evaluation pipelines. |
| `MEMORY` | A memory read or write operation. |
| `MCP_TOOL` | MCP protocol tool handlers. |
| `LLM` | A model call. **Not accepted by `@span()`** — create via `neatlogs.trace(kind="LLM")` to attach prompt templates. |
| `VECTOR_STORE` | A vector DB write/query. **Not accepted by `@span()`** — create via `neatlogs.trace()`. |

## Migration table: OpenLLMetry `openinference.span.kind` → NeatLogs kind

This is the heart of step 5. The `openinference.span.kind`
attribute (added by OpenLLMetry's auto-instrumentation or
by your manual `set_attribute` call) maps to a NeatLogs
kind.

| OpenInference `span_kind` | What it is | NeatLogs |
|---|---|---|
| (not set) | A generic span — function call, sub-step | `@neatlogs.span(kind="CHAIN", name=...)` (the closest default; if it's a tool, use TOOL) |
| `"LLM"` | An LLM call (chat completion) | `with neatlogs.trace("name", kind="LLM", system_prompt_template=..., user_prompt_template=...)` |
| `"TOOL"` | A tool the agent calls | `@neatlogs.span(kind="TOOL", tool_name=..., description=...)` |
| `"CHAIN"` | Sequential steps | `@neatlogs.span(kind="CHAIN", name=...)` |
| `"AGENT"` | The agent decision loop | `@neatlogs.span(kind="AGENT", name=...)` |
| `"RETRIEVER"` | RAG fetch | `@neatlogs.span(kind="RETRIEVER")` |
| `"EMBEDDING"` | Text → vector | `@neatlogs.span(kind="EMBEDDING")` |
| `"RERANKER"` | Re-orders candidate docs | `with neatlogs.trace("name", kind="RERANKER")` (trace-only) |
| `"EVALUATOR"` | Scoring / grading | `@neatlogs.span(kind="GUARDRAIL")` (EVALUATOR is the OpenInference name; NeatLogs' closest is GUARDRAIL) |
| `"MEMORY"` | Memory read or write | `@neatlogs.span(kind="AGENT")` (or wrap with a `MEMORY` kind if the SDK exposes it) |
| `"PARSER"` | Output parser | `@neatlogs.span(kind="CHAIN", name=...)` (parsers are typically just CHAIN; LLM is on the model call that produced the parsed text) |
| `"EMBEDDING"` | Same as above | (same) |

Note: OpenInference's `"EVALUATOR"` is a different shape from
NeatLogs' `kind="GUARDRAIL"`. OpenInference uses EVALUATOR
specifically for evaluation runs (datasets, scoring);
NeatLogs uses GUARDRAIL for any "validates / filters /
scores content" operation. If the OpenInference span is
genuinely an evaluation pipeline (not a content guard),
consider keeping it as a plain attribute
(`openinference.span.kind=EVALUATOR`) and using
`@neatlogs.span(kind="GUARDRAIL")` for the kind itself, or
leave the span uncategorized in NeatLogs and let the
OpenInference attribute drive the dashboard's
EVALUATOR-grouped view (if the dashboard supports it).

## How the choice propagates

`@neatlogs.span(kind="AGENT")` on `researcher()` makes that
function the AGENT root. Calls made inside `researcher()`
(LLM, tools, other spans) become children. The dashboard
groups by AGENT for per-agent analytics, by LLM for
cost-per-model, by TOOL for per-tool latency, by
EVALUATOR for per-evaluation analytics.

If you have a function that does:
```python
tracer = trace.get_tracer(__name__)
def pipeline(query):
    with tracer.start_as_current_span("pipeline", attributes={"openinference.span.kind": "CHAIN"}):
        user_input = ...
        response = openai_client.chat.completions.create(...)
    return response.choices[0].message.content
```

The NeatLogs equivalent is **NOT**
`@neatlogs.span(kind="LLM")` — that span would lack the
surrounding context. It's:
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

The outer CHAIN holds the user input and the LLM span. The
inner LLM span holds the prompt and tokens. Both are visible
in the dashboard; the cost/analytics split correctly.

## The decorator vs. context manager choice

- `@neatlogs.span(kind=...)` for a whole function (the
  common case). Span attrs (input, output, name) come from
  the function's args and return value.
- `with neatlogs.trace("name", kind=...)` for a block inside
  a function (e.g. just the LLM call, not the surrounding
  orchestration). Span attrs come from `set_attribute()`
  calls inside the block.
- **Trace-only kinds** (`LLM`, `VECTOR_STORE`, `RERANKER`)
  must use `trace()`, not `span()`.

If the original `tracer.start_as_current_span` covered the
whole function, use `@neatlogs.span`. If it covered only a
block, use `trace()`.

## Forbidden: don't put a `@span` on top of an already-wrapped call

The NeatLogs trace processor auto-creates a WORKFLOW root
for a wrapped LLM call (e.g.
`client = neatlogs.wrap(OpenAI()); client.chat.completions.create(...)`).
Adding `@neatlogs.span(kind="LLM")` on top of that creates
duplicate spans. The pattern is:

- `@neatlogs.span(kind=...)` for YOUR orchestration code
  only.
- LLM spans on the wrapped call happen automatically; do
  not add another decorator.
- For prompt management: wrap the LLM call with
  `with neatlogs.trace("name", kind="LLM",
  system_prompt_template=...)` INSIDE the orchestration.
  This adds prompt-template context to the auto-LLM-span
  without creating a new span.

## OpenLLMetry-specific note

If the project uses `opentelemetry-instrumentation-*`
auto-instrumentation, the auto-instrumentation adds
`openinference.span.kind` attributes to spans. After the
migration, the NeatLogs kind is set via the
`@neatlogs.span(kind=...)` decorator or the
`neatlogs.trace(kind="LLM", ...)` context manager. The
`openinference.span.kind` attribute can stay on the span as
plain metadata (NeatLogs preserves arbitrary attributes);
the dashboard's `kind` column is driven by the NeatLogs
attribute, not the OpenInference one. The migration's
`@neatlogs.span(kind="AGENT")` decorators become the
authoritative source of truth for the `kind` taxonomy.
