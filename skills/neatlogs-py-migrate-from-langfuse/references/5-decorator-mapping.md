# Step 5: Decorator mapping — Path B fallback

## When to do this step

Do this step only if step 1 classified the project as **Path B
(native Langfuse SDK)** — i.e. you have `from langfuse import
Langfuse` and the code calls `lf.update_current_span(...)`,
`lf.score_current_span(...)`, or uses `@observe(...)` decorators.

If step 4 already gets the project the traces it needs, **skip this
step**. The decorator-mapping content here is for the 10% case
where the native SDK is the project's only Langfuse integration.

## What "mapping" means

The native Langfuse SDK and the NeatLogs SDK have different APIs
for the same intent. You can replace Langfuse's decorator
annotations with NeatLogs equivalents without rewriting the
business logic.

| Langfuse (v2 native SDK) | NeatLogs |
|---|---|
| `@observe()` on a function | `@neatlogs.span(kind="AGENT", name=...)` |
| `@observe(as_type="generation")` on a chat call | `with neatlogs.trace("name", kind="LLM", system_prompt_template=..., user_prompt_template=...)` |
| `lf.update_current_span(name=...)` | (rename the function or set `name=` on the span) |
| `lf.update_current_span(input=...)` / `output=...` | NeatLogs captures the function's args + return automatically; no manual update needed |
| `lf.score_current_span(name="quality", value=0.9)` | `span.set_attribute("neatlogs.user.score", 0.9)` |
| `lf.update_current_span(metadata={"k": "v"})` | `span.set_attribute("k", "v")` |
| `lf.flush()` | `neatlogs.flush()` |
| `lf.shutdown()` | `neatlogs.shutdown()` |
| `Langfuse()` client construction | (delete the call; NeatLogs init is global per process, no per-tracer client) |

Note: NeatLogs auto-captures `input` and `output` from the wrapped
function's arguments and return value. If you do not want this
(e.g. for PII reasons), pass `capture_input=False` /
`capture_output=False` to the span, or set a `mask=` callback.

## Action

1. For each file in step 1's grep result, edit the import lines:
   ```python
   # ❌ BEFORE
   from langfuse import Langfuse
   from langfuse.decorators import observe, langfuse_context

   # ✅ AFTER
   import neatlogs
   from neatlogs import SystemPromptTemplate, UserPromptTemplate  # only if used
   ```
2. For each `@observe(...)` decorator on a function, replace per the
   table above. **Do NOT** just rename the decorator — change the
   `kind=` and the call style.

   ```python
   # ❌ BEFORE
   @observe()
   def research(question: str) -> str:
       resp = openai_client.chat.completions.create(...)
       return resp.choices[0].message.content

   # ✅ AFTER
   @neatlogs.span(kind="AGENT", name="research")
   def research(question: str) -> str:
       resp = openai_client.chat.completions.create(...)
       return resp.choices[0].message.content
   ```
3. For each `lf.update_current_span(...)` call, replace per the table.
   If the original code was setting `input` / `output` on the span,
   **remove those calls** — NeatLogs auto-captures them. If the
   original code was setting `metadata`, convert to `span.set_attribute(...)`.
4. For each `lf.score_current_span(...)` call, replace with
   `span.set_attribute("neatlogs.user.score", value)`.
5. For the LLM call inside the function, wrap with `neatlogs.trace("name",
   kind="LLM", system_prompt_template=..., user_prompt_template=...)`
   if you want prompt templates to show up in the NeatLogs prompt
   management dashboard. Templates must be compiled and the compiled
   output passed into the call.

   ```python
   @neatlogs.span(kind="AGENT", name="research")
   def research(question: str) -> str:
       sys_tpl = SystemPromptTemplate([{"role": "system", "content": "You are concise."}])
       user_tpl = UserPromptTemplate([{"role": "user", "content": "{{q}}"}])
       with neatlogs.trace("llm_call", kind="LLM",
                           system_prompt_template=sys_tpl,
                           user_prompt_template=user_tpl):
           msgs = sys_tpl.compile() + user_tpl.compile(q=question)
           resp = openai_client.chat.completions.create(model="gpt-4o", messages=msgs)
       return resp.choices[0].message.content
   ```
6. If the project uses `Langfuse()` as a context-managed client
   (e.g. `with Langfuse() as lf:`), the `with` block is no longer
   needed. NeatLogs init is process-global. Delete the `with` block.
7. Replace `lf.flush()` / `lf.shutdown()` with `neatlogs.flush()` /
   `neatlogs.shutdown()` at process exit (scripts) or in the
   server's shutdown hook (FastAPI/Flask lifespan / atexit).

## What this is NOT

- It is **not** a Codemod. Do not run a regex replacement across the
  whole codebase. `@observe()` has parameters that `@neatlogs.span()`
  doesn't (`as_type=`, `name=`, `capture_input=`); a `kind=` choice
  depends on the function's role; some `@observe` calls map to
  `AGENT`, some to `CHAIN`, some to `TOOL`. Each one is a manual edit
  (or a focused AST refactor if the user is up for it).
- It is **not** auto-verified. Run the project after each file's
  edits and check the NeatLogs dashboard to confirm spans are still
  landing.

## When the function is a tool, not an agent

If `@observe` is on a function the agent CALLS (not the agent
itself), the migration is `kind="TOOL"`, not `kind="AGENT"`:

```python
# ❌ BEFORE
@observe(as_type="span")
def web_search(query: str) -> str:
    return search_api(query)

# ✅ AFTER
@neatlogs.span(kind="TOOL", tool_name="web_search",
               description="Search the web for the given query")
def web_search(query: str) -> str:
    return search_api(query)
```

## Verify BEFORE moving to step 6

1. All `from langfuse import ...` lines are gone.
2. All `@observe(...)` decorators are replaced (grep returns 0
   matches).
3. All `lf.update_current_span(...)` / `lf.score_current_span(...)` /
   `lf.flush()` / `lf.shutdown()` are replaced.
4. The app still runs. Trigger a request; verify the same trace
   shape appears in the NeatLogs dashboard that previously appeared
   in Langfuse (one WORKFLOW root, nested AGENT/TOOL/LLM children,
   session grouping if the project used sessions).
5. No duplicate spans: the project should NOT have BOTH a Langfuse
   span AND a NeatLogs span for the same logical operation. (Step 6
   removes the Langfuse side; until then, this is a sanity check.)
