# Step 5: Decorator mapping — Path B fallback

## When to do this step

Do this step only if step 1 classified the project as **Path B
(explicit LangSmith SDK)** — i.e. you have `from langsmith import
traceable` (or `from langsmith import trace`) and the code uses
`@traceable(...)` decorators or constructs `RunTree(...)`
directly.

If step 4 already gets the project the traces it needs, **skip
this step**. The decorator-mapping content here is for the 10%
case where the explicit SDK is the project's only LangSmith
integration.

## What "mapping" means

The LangSmith SDK and the NeatLogs SDK have different APIs for
the same intent. You can replace LangSmith's decorator
annotations and RunTree calls with NeatLogs equivalents
without rewriting the business logic.

## LangSmith → NeatLogs API table

| LangSmith (v0.x) | NeatLogs |
|---|---|
| `@traceable` on a function (no `run_type` arg) | `@neatlogs.span(kind="AGENT", name=...)` |
| `@traceable(run_type="llm")` on a chat call | `with neatlogs.trace("name", kind="LLM", system_prompt_template=..., user_prompt_template=...)` |
| `@traceable(run_type="tool")` on a tool function | `@neatlogs.span(kind="TOOL", tool_name=..., description=...)` |
| `@traceable(run_type="chain")` on a multi-step orchestrator | `@neatlogs.span(kind="CHAIN", name=...)` |
| `@traceable(run_type="retriever")` on a RAG fetch | `@neatlogs.span(kind="RETRIEVER")` |
| `@trace` (older; predates `traceable`) | Same as `@traceable`; replace with the matching `kind=` |
| `langsmith_client.create_run(name=..., inputs=..., outputs=...)` | (replace with a NeatLogs span; the SDK captures inputs/outputs automatically) |
| `RunTree.from_chain(...).post(...)` | `with neatlogs.trace("name", kind="CHAIN", ...)` + `span.set_attribute(...)` for inputs/outputs |
| `RunTree.from_llm(...).post(outputs=...)` | `with neatlogs.trace("name", kind="LLM", ...)` + `span.set_attribute("neatlogs.llm.output", ...)` |
| `RunTree.from_tool(...).post(output=...)` | `@neatlogs.span(kind="TOOL", ...)` |
| `RunTree.from_retriever(...).post(outputs=...)` | `@neatlogs.span(kind="RETRIEVER", ...)` |
| `RunTree(metadata={...})` | `span.set_attribute("k", "v")` (one per metadata key) |
| `client.run_on_thread(...)` | (no equivalent in NeatLogs v1; thread tracking not supported — flag in the skill) |
| `client.flush()` | `neatlogs.flush()` |
| `client.delete_project(...)` (cleanup) | (no equivalent; NeatLogs projects are derived from `workflow_name`) |
| `client.read_run(...)` (post-hoc query) | (no equivalent; use the NeatLogs dashboard / REST API) |

Note: NeatLogs auto-captures `input` and `output` from the
wrapped function's arguments and return value. If you do not
want this (e.g. for PII reasons), pass `capture_input=False` /
`capture_output=False` to the span, or set a `mask=` callback.

## The `@traceable` parameters that don't map

`@traceable` has parameters that `@neatlogs.span` doesn't have.
Before replacing, audit each call site for these:

| `@traceable` parameter | What to do |
|---|---|
| `run_type` | → `kind=` on `@neatlogs.span` (or `kind=` on `neatlogs.trace` for non-decorator cases) |
| `name` | → `name=` on `@neatlogs.span` (or `name=` on `neatlogs.trace`) |
| `tags` (a list of strings) | → `span.set_attribute("langsmith.tag.<i>", tag)` for each tag (no list-valued span attrs in OTel) |
| `metadata` (a dict) | → `span.set_attribute("k", "v")` for each key |
| `client` (a custom LangSmith client) | → delete; NeatLogs init is process-global |
| `metadata` arg inside `RunTree.from_*().post(...)` | → `span.set_attribute("k", "v")` |
| `extras` (arbitrary dict on `post`) | → `span.set_attribute("extras.k", "v")` |
| `tags` arg on `RunTree.post(...)` | → `span.set_attribute("langsmith.tag.<i>", tag)` |
| `replicate=False` (don't auto-push to LangSmith) | → delete; the NeatLogs span always records to the active tracer |

## Action

1. For each file in step 1's grep result, edit the import lines:
   ```python
   # ❌ BEFORE
   from langsmith import traceable, Client
   from langsmith.run_trees import RunTree

   # ✅ AFTER
   import neatlogs
   from neatlogs import SystemPromptTemplate, UserPromptTemplate  # only if used
   ```
2. For each `@traceable(...)` decorator on a function, replace per
   the table above. **Do NOT** just rename the decorator — change
   the `kind=` and the call style.

   ```python
   # ❌ BEFORE
   @traceable(run_type="chain")
   def research(question: str) -> str:
       resp = openai_client.chat.completions.create(...)
       return resp.choices[0].message.content

   # ✅ AFTER
   @neatlogs.span(kind="CHAIN", name="research")
   def research(question: str) -> str:
       resp = openai_client.chat.completions.create(...)
       return resp.choices[0].message.content
   ```
3. For each `@traceable(run_type="llm")` decorator, switch from
   `@traceable` to `with neatlogs.trace(...)`:
   ```python
   # ❌ BEFORE
   @traceable(run_type="llm")
   def ask_openai(prompt: str) -> str:
       resp = openai_client.chat.completions.create(model="gpt-4o", messages=[...])
       return resp.choices[0].message.content

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
4. For each `RunTree.from_chain(...).post(...)` /
   `RunTree.from_llm(...).post(...)` / `RunTree.from_tool(...).post(...)`
   block, replace per the table. Set `name` and `kind` from the
   `from_*` call. If the original code was setting `inputs` /
   `outputs` on the RunTree, those become `span.set_attribute(...)`
   on the corresponding NeatLogs span (or are auto-captured).
5. If the project uses `langsmith_client.run_on_thread(...)`,
   the equivalent in NeatLogs is to wrap the per-thread work in
   `with neatlogs.trace(...)`. NeatLogs v1 does not have a
   per-thread tree API; the trace goes on the active span's
   context, and the dashboard's per-thread view comes from the
   `neatlogs.session.id` attribute (set via `identify()`).
6. Replace `client.flush()` / `client.delete_project(...)` calls
   with `neatlogs.flush()` (or remove — projects are derived
   from `workflow_name`).
7. If the project uses LangChain's `langchain.observability`
   callback (v0.3+), the callback is registered globally; the
   OTel exporter in step 4 now receives the LangChain spans. No
   code change needed for the callback path.

## What this is NOT

- It is **not** a Codemod. Do not run a regex replacement across
  the whole codebase. `@traceable` has parameters
  (`run_type=`, `name=`, `tags=`, `metadata=`, `client=`,
  `replicate=`) that `@neatlogs.span` doesn't have; a `kind=`
  choice depends on the function's role; some `@traceable` calls
  map to `AGENT`, some to `CHAIN`, some to `TOOL`. Each one is
  a manual edit (or a focused AST refactor if the user is up for
  it).
- It is **not** auto-verified. Run the project after each file's
  edits; final confirmation comes from the SKILL.md live
  completion gate (a marker-matched, nonce-qualified persisted
  trace), not from a dashboard glance.
- It does **not** replicate LangSmith's eval / dataset / feedback
  surfaces. NeatLogs has no eval. If the project depends on
  `langchain smith` for CI evals, stay on LangSmith for that
  part; only the observability backend is being swapped.

## When the function is a tool, not an agent

If `@traceable` is on a function the agent CALLS (not the agent
itself), the migration is `kind="TOOL"`, not `kind="AGENT"`:

```python
# ❌ BEFORE
@traceable(run_type="tool")
def web_search(query: str) -> str:
    return search_api(query)

# ✅ AFTER
@neatlogs.span(kind="TOOL", tool_name="web_search",
               description="Search the web for the given query")
def web_search(query: str) -> str:
    return search_api(query)
```

## Verify BEFORE moving to step 6

1. All `from langsmith import ...` lines are gone.
2. All `@traceable(...)` and `@trace(...)` decorators are
   replaced (grep returns 0 matches).
3. All `RunTree(...)` constructions and `.post(...)` calls
   are replaced.
4. All `langsmith_client.flush()` / `delete_project(...)` calls
   are replaced or removed.
5. The app still runs. Trigger a request; verify the same trace
   shape that previously appeared in LangSmith now lands in
   NeatLogs (one WORKFLOW root, nested AGENT/TOOL/
   LLM children, session grouping if the project used sessions),
   confirmed through the SKILL.md live completion gate.
6. No duplicate spans: the project should NOT have BOTH a
   LangSmith span AND a NeatLogs span for the same logical
   operation. (Step 6 removes the LangSmith side; until then,
   this is a sanity check.)
