# Step 5: Decorator / span mapping — Path B fallback

## When to do this step

Do this step only if step 1 classified the project as **Path B
(manual `tracer.start_as_current_span`)** — i.e. you have
`trace.get_tracer(__name__)` and the code uses
`with tracer.start_as_current_span("name", ...)` directly,
or chains its own `BatchSpanProcessor` instances.

If step 4 already gets the project the traces it needs, **skip
this step**. The decorator-mapping content here is for the 10%
case where the project has manual OpenInference spans in
addition to (or instead of) auto-instrumentation.

## What "mapping" means

The OTel SDK and the NeatLogs SDK have different APIs for the
same intent. You can replace manual `tracer.start_as_current_span`
calls with NeatLogs equivalents without rewriting the business
logic.

## OTel SDK → NeatLogs API table

| OTel SDK (Path B) | NeatLogs |
|---|---|
| `with tracer.start_as_current_span("name"):` (no kind, no attrs) | `@neatlogs.span(kind="CHAIN", name="name")` on the function (default; or AGENT/TOOL based on context) |
| `with tracer.start_as_current_span("name", attributes={"openinference.span.kind": "LLM"})` | `with neatlogs.trace("name", kind="LLM", system_prompt_template=..., user_prompt_template=...)` |
| `with tracer.start_as_current_span("name", attributes={"openinference.span.kind": "TOOL"})` | `@neatlogs.span(kind="TOOL", tool_name="name", description=...)` |
| `with tracer.start_as_current_span("name", attributes={"openinference.span.kind": "AGENT"})` | `@neatlogs.span(kind="AGENT", name="name")` |
| `with tracer.start_as_current_span("name", attributes={"openinference.span.kind": "CHAIN"})` | `@neatlogs.span(kind="CHAIN", name="name")` |
| `with tracer.start_as_current_span("name", attributes={"openinference.span.kind": "RETRIEVER"})` | `@neatlogs.span(kind="RETRIEVER")` |
| `with tracer.start_as_current_span("name", attributes={"openinference.span.kind": "EMBEDDING"})` | `@neatlogs.span(kind="EMBEDDING")` |
| `with tracer.start_as_current_span("name", attributes={"openinference.span.kind": "EVALUATOR"})` | `@neatlogs.span(kind="GUARDRAIL")` |
| `with tracer.start_as_current_span("name", attributes={"openinference.span.kind": "RERANKER"})` | `with neatlogs.trace("name", kind="RERANKER")` (RERANKER is trace-only) |
| `span.set_attribute("openinference.entity.llm.model_name", "gpt-4o")` | `span.set_attribute("neatlogs.llm.model", "gpt-4o")` (or keep `openinference.*` — NeatLogs preserves arbitrary attributes) |
| `span.set_attribute("openinference.llm.token_count.prompt", 123)` | `span.set_attribute("neatlogs.llm.input_tokens", 123)` |
| `span.set_attribute("openinference.llm.token_count.completion", 45)` | `span.set_attribute("neatlogs.llm.output_tokens", 45)` |
| `span.set_attribute("openinference.input.value", prompt_text)` | (NeatLogs auto-captures the wrapped function's args; no manual set) |
| `span.set_attribute("openinference.output.value", response_text)` | (NeatLogs auto-captures the wrapped function's return) |
| `span.set_status(Status(StatusCode.OK))` | (no NeatLogs equivalent; status is derived from span attributes) |
| `span.record_exception(e)` | `span.set_attribute("exception", str(e))` (or let the `@neatlogs.span` decorator auto-capture via `try/except` wrapping) |
| `tracer = trace.get_tracer(__name__)` | (delete; NeatLogs init is process-global) |
| `provider.add_span_processor(BatchSpanProcessor(exporter))` | (delete; NeatLogs manages its own exporter) |
| `trace.set_tracer_provider(TracerProvider())` | (delete; do not override the OTel global — NeatLogs hooks via env vars + auto-instrumentation, not a custom provider) |

Note: NeatLogs auto-captures `input` and `output` from the
wrapped function's arguments and return value. If you do not
want this (e.g. for PII reasons), pass `capture_input=False` /
`capture_output=False` to the span, or set a `mask=` callback.

## The `attributes` parameter that doesn't map

`tracer.start_as_current_span` takes an `attributes` dict. Some
of those keys are OpenInference semantic conventions; some are
project-specific. The `openinference.*` keys can stay as plain
attributes (NeatLogs preserves them). The non-OpenInference keys
need to be reviewed per call site — most of them are
project-specific and should stay as plain attributes; some are
NeatLogs-mappable (token counts, model name, etc.).

Before replacing, audit each call site for these:

| Attribute key | What to do |
|---|---|
| `openinference.span.kind` | → `kind=` on `@neatlogs.span` (or `kind=` on `neatlogs.trace` for non-decorator cases) |
| `openinference.entity.llm.model_name` | → `span.set_attribute("neatlogs.llm.model", ...)` (or keep `openinference.*` for cross-tooling compatibility) |
| `openinference.llm.token_count.prompt` | → `span.set_attribute("neatlogs.llm.input_tokens", ...)` |
| `openinference.llm.token_count.completion` | → `span.set_attribute("neatlogs.llm.output_tokens", ...)` |
| `openinference.input.value` | (delete; NeatLogs auto-captures from the function's args) |
| `openinference.output.value` | (delete; NeatLogs auto-captures from the function's return) |
| `openinference.llm.system`, `openinference.llm.user` | → wrap the LLM call with `neatlogs.trace(kind="LLM", system_prompt_template=..., user_prompt_template=...)` |
| `custom.k1`, `custom.k2` (project-specific) | → keep as plain `set_attribute("custom.k1", v)` calls; no change needed |
| `record_exception=True` | → `span.set_attribute("exception", str(e))` in a `try/except` block |

## Action

1. For each file in step 1's grep result, edit the imports:
   ```python
   # ❌ BEFORE
   from opentelemetry import trace
   from opentelemetry.instrumentation.openai import OpenAIInstrumentor

   # ✅ AFTER
   import neatlogs
   from neatlogs import SystemPromptTemplate, UserPromptTemplate  # only if used
   ```
2. For each `with tracer.start_as_current_span(...)` block, replace
   per the table. If the span is a function-level annotation,
   switch to `@neatlogs.span(kind=...)`:
   ```python
   # ❌ BEFORE
   def research(question: str) -> str:
       tracer = trace.get_tracer(__name__)
       with tracer.start_as_current_span("research",
                                        attributes={"openinference.span.kind": "AGENT"}):
           resp = openai_client.chat.completions.create(...)
       return resp.choices[0].message.content

   # ✅ AFTER
   @neatlogs.span(kind="AGENT", name="research")
   def research(question: str) -> str:
       resp = openai_client.chat.completions.create(...)
       return resp.choices[0].message.content
   ```
3. For each `with tracer.start_as_current_span(...)` block where
   the OpenInference `span_kind` is `LLM`, switch to
   `neatlogs.trace(kind="LLM", ...)`:
   ```python
   # ❌ BEFORE
   tracer = trace.get_tracer(__name__)
   with tracer.start_as_current_span("llm_call",
                                    attributes={"openinference.span.kind": "LLM",
                                                "openinference.entity.llm.model_name": "gpt-4o"}):
       resp = openai_client.chat.completions.create(model="gpt-4o", messages=[...])

   # ✅ AFTER
   def ask_openai(prompt: str) -> str:
       sys_tpl = SystemPromptTemplate([{"role": "system", "content": "You are concise."}])
       user_tpl = UserPromptTemplate([{"role": "user", "content": "{{q}}"}])
       with neatlogs.trace("llm_call", kind="LLM",
                           system_prompt_template=sys_tpl,
                           user_prompt_template=user_tpl):
           msgs = sys_tpl.compile() + user_tpl.compile(q=prompt)
           resp = openai_client.chat.completions.create(model="gpt-4o", messages=msgs)
       return resp.choices[0].message.content
   ```
4. If the project has its own `BatchSpanProcessor` chain, decide:
   if all the spans in the chain are also covered by `@neatlogs.span`
   decorators, delete the chain. If some spans are still going
   through the OTel SDK directly (e.g. a `tracer.start_as_current_span`
   you couldn't rewrite), keep the chain but ensure the OTel SDK
   `TracerProvider` is set up to send to NeatLogs.
5. If the project calls `trace.set_tracer_provider(...)` to
   override the OTel global, **stop and verify with the
   maintainers first**. NeatLogs auto-instrumentation hooks via
   the env-var-configured OTel SDK; overriding the global
   `TracerProvider` mid-process can break NeatLogs auto-
   instrumentation silently. Step 6 will detect this via the
   live-trace gate; if it does, refactor to keep the default
   OTel global and use `@neatlogs.span` for NeatLogs-specific
   spans.

## What this is NOT

- It is **not** a Codemod. Do not run a regex replacement across
  the whole codebase. `tracer.start_as_current_span` has
  parameters (`attributes=`, `kind=`, `links=`, `start_time=`,
  `record_exception=`, `set_status_on_exception=`) that
  `@neatlogs.span` doesn't have; a `kind=` choice depends on
  the function's role; some calls map to `AGENT`, some to
  `CHAIN`, some to `TOOL`. Each one is a manual edit (or a
  focused AST refactor if the user is up for it).
- It is **not** auto-verified. Run the project after each
  file's edits and check the NeatLogs dashboard to confirm
  spans are still landing. Step 6's live-trace gate is the
  authoritative verification.
- It does **not** replicate OpenInference evaluation surfaces
  (Phoenix eval API, OpenInference `evaluator` package). Those
  are out of scope. If the project depends on them, stay on
  OpenLLMetry for that part.

## When the function is a tool, not an agent

If `tracer.start_as_current_span` is on a function the agent
CALLS (not the agent itself), the migration is
`@neatlogs.span(kind="TOOL", ...)`, not `AGENT`:

```python
# ❌ BEFORE
tracer = trace.get_tracer(__name__)
def web_search(query: str) -> str:
    with tracer.start_as_current_span("web_search",
                                     attributes={"openinference.span.kind": "TOOL"}):
        return search_api(query)

# ✅ AFTER
@neatlogs.span(kind="TOOL", tool_name="web_search",
               description="Search the web for the given query")
def web_search(query: str) -> str:
    return search_api(query)
```

## Verify BEFORE moving to step 6

1. All `from opentelemetry...` / `from openinference...` imports
   that you intended to replace are gone.
2. All `with tracer.start_as_current_span(...)` blocks you
   intended to replace are converted.
3. All `tracer = trace.get_tracer(...)` and
   `trace.set_tracer_provider(...)` calls are gone (unless
   intentionally kept for a non-replaced span).
4. The app still runs. The NeatLogs dashboard should be
   receiving spans (step 4's endpoint swap). The exact same
   trace shape appears in the NeatLogs dashboard that
   previously appeared in your OTel collector (one WORKFLOW
   root, nested AGENT/TOOL/LLM children, session grouping if
   the project used sessions).
5. No duplicate spans: the project should NOT have BOTH an OTel
   span AND a NeatLogs span for the same logical operation.
   (Step 6 removes the OpenLLMetry side; until then, this is
   a sanity check.)
