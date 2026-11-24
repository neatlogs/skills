# Step 4: Identify and Decorate Functions

## The One Rule That Matters Most

Ask yourself for EVERY function: **"Is this function directly triggered by the user (CLI command, HTTP endpoint, job), or is it internal?"**

- User-triggered → `@span(kind="WORKFLOW")` — this is the TRACE ROOT
- Internal orchestrator (calls other functions but no LLM call itself) → `@span(kind="CHAIN")`
- Contains an LLM API call → `@span(kind="CHAIN")`
- Discrete I/O or tool capability → `@span(kind="TOOL")` [Step 6]

## WRONG vs RIGHT — Classification

```python
# ❌ WRONG — run_pipeline is NOT a WORKFLOW. It's internal. Nobody calls it directly.
@neatlogs.span(kind="WORKFLOW")
def run_pipeline(text, settings):
    return asyncio.run(process_document(text, settings))

# ❌ WRONG — process_document is NOT a WORKFLOW. It's an internal orchestrator.
@neatlogs.span(kind="WORKFLOW")
async def process_document(text, settings):
    chunks = chunk_text(text)
    results = await asyncio.gather(...)
    return combine(results)

# ✅ RIGHT — the click command IS the user-facing entry point. THIS is the WORKFLOW.
@cli.command()
@click.argument("file_path")
@neatlogs.span(kind="WORKFLOW", name="process")
def process(file_path: str):
    text = read_document(file_path)
    result = run_pipeline(text, settings)
    write_document(result.report, output_path)

# ✅ RIGHT — internal orchestrators are CHAIN
@neatlogs.span(kind="CHAIN", name="run_pipeline")
def run_pipeline(text, settings):
    return asyncio.run(process_document(text, settings))

@neatlogs.span(kind="CHAIN", name="process_document")
async def process_document(text, settings):
    chunks = chunk_text(text)
    results = await asyncio.gather(...)
    return combine(results)
```

## Why This Matters: Trace Context Binding

All spans in one execution MUST share one trace. Spans inherit their parent's trace context. If a decorated function is called from an UNDECORATED function, it starts a NEW orphan trace.

```
# What happens WITHOUT decorating the CLI command:
process() [no span]
  ├── read_document()  → orphan trace A (lost!)
  ├── run_pipeline()   → orphan trace B
  └── write_document() → orphan trace C (lost!)

# What happens WITH the CLI command as WORKFLOW:
process() [WORKFLOW span — trace root]
  ├── read_document()  → child of process (same trace!)
  ├── run_pipeline()   → child of process (same trace!)
  │     └── process_document() → grandchild (same trace!)
  └── write_document() → child of process (same trace!)
```

## Decision Tree

**Each FEATURE is its own independent WORKFLOW = one trace root.** A service has many features —
every route handler, every CLI sub-command, every queue/cron consumer, every public library entry
point is a SEPARATE, independent workflow. They are SIBLINGS (each its own trace), never nested under
one another and never collapsed into a single app-wide workflow. The CHAIN/LLM/TOOL/RETRIEVER spans a
feature uses nest UNDER that feature's WORKFLOW root.

For each function, answer in order:

1. **Is it a user-facing entry point / a feature?** (FastAPI route, click command, celery/queue/kafka
   consumer handler, cron job, `main()`, a public library function a caller invokes directly)
   → YES → `@span(kind="WORKFLOW")` — this is an independent trace root.

   ⚠️ STREAMING / SSE entry points (the handler RETURNS a `StreamingResponse` / `EventSourceResponse` /
   a generator): do NOT use a `@span` decorator on the handler. It returns immediately, so the span
   closes BEFORE the generator runs — the streamed children then fire with no active parent and scatter
   into separate orphan traces. Open the WORKFLOW span INSIDE the generator instead:
   ```python
   # ❌ WRONG — decorator closes when the StreamingResponse is returned, orphaning the stream
   @neatlogs.span(kind="WORKFLOW", name="chat")
   async def chat(...):
       return StreamingResponse(event_gen(), media_type="text/event-stream")

   # ✅ RIGHT — instrument typed app events inside the generator before SSE wire encoding
   import json
   import re
   from starlette.responses import StreamingResponse

   MAX_PREVIEW_CHARS = 4096
   MAX_SANITIZE_CHARS = MAX_PREVIEW_CHARS * 2  # sanitize bounded lookahead before clipping
   _EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
   _BEARER_RE = re.compile(r"(?i)\b(?:authorization\s*:\s*)?bearer\s+\S+")
   _API_KEY_RE = re.compile(
       r"(?:(?<![A-Za-z0-9])(?:sk|pk|nl[a-z]{0,2})[-_][A-Za-z0-9_-]{12,}|(?i:\bx-api-key\s*:\s*\S+))"
   )
   _TRAILING_EMAIL_FRAG_RE = re.compile(r"(?:^|(?<=\s))\S*@\S*$")
   _TRAILING_KEY_FRAG_RE = re.compile(r"(?:(?<![A-Za-z0-9])(?:sk|pk|nl[a-z]{0,2})[-_]\S*$)")


   def _redact_pii(text: str) -> str:
       # Substitute your app's PII/secret scrubber (or configure neatlogs.init(mask=...))
       text = _BEARER_RE.sub("[REDACTED_TOKEN]", text)
       text = _API_KEY_RE.sub("[REDACTED_SECRET]", text)
       return _EMAIL_RE.sub("[REDACTED_EMAIL]", text)


   def _sanitize_and_bound(text: str, *, already_truncated: bool = False) -> tuple[str, bool]:
       exceeded = already_truncated or len(text) > MAX_SANITIZE_CHARS
       window = text[:MAX_SANITIZE_CHARS]
       if exceeded:
           window = _TRAILING_EMAIL_FRAG_RE.sub("[REDACTED_EMAIL]", window)
           window = _TRAILING_KEY_FRAG_RE.sub("[REDACTED_SECRET]", window)
       sanitized = _redact_pii(window)
       if len(sanitized) > MAX_PREVIEW_CHARS:
           clipped = _TRAILING_EMAIL_FRAG_RE.sub("", sanitized[:MAX_PREVIEW_CHARS])
           return clipped, True
       return sanitized, exceeded


   def _safe_str_attr(obj, name: str) -> str | None:
       try:
           val = getattr(obj, name, None)
           return val if isinstance(val, str) and val else None
       except Exception:
           return None


   def _project_request_input(req) -> tuple[dict[str, object], bool]:
       # Approved, sanitized application-level projection — never raw request bodies
       text = _safe_str_attr(req, "message") or ""
       sanitized, truncated = _sanitize_and_bound(text)
       projection: dict[str, object] = {"message": sanitized}
       if truncated:
           projection["truncated"] = True
       return projection, truncated


   def _format_sse(ev) -> str:
       # Wire encoder stays separate from telemetry; replace with your app's SSE serializer
       raw_kind = ev.get("kind", "message") if isinstance(ev, dict) else getattr(ev, "kind", "message")
       kind = raw_kind.replace("\r", "").replace("\n", "") if isinstance(raw_kind, str) and raw_kind else "message"
       payload = (
           (ev.get("text", "") if isinstance(ev, dict) else getattr(ev, "text", ""))
           if kind == "delta"
           else {"kind": kind}
       )
       return f"event: {kind}\ndata: {json.dumps(payload)}\n\n"


   async def chat(req):
       # event_gen(req) yields typed app events (kind in {"delta", "done", "error", "debug"})
       async def traced_gen():
           preview_parts: list[str] = []
           buffered_len = 0
           completed = False
           saw_done = False
           saw_error = False
           capture_failed = False
           preview_truncated = False
           input_truncated = False
           with neatlogs.trace(
               "chat",
               kind="WORKFLOW",
               session_id=_safe_str_attr(req, "conversation_id"),
               end_user_id=_safe_str_attr(req, "user_id"),
               # Requires neatlogs >= 1.5.0 (omit prompt_version on v1.4.x)
               prompt_version="chat-v2",
           ) as span:
               try:
                   input_projection, input_truncated = _project_request_input(req)
                   span.set_attribute("input.value", json.dumps(input_projection))
               except Exception:
                   pass  # input projection / attribute errors must never disrupt the stream
               try:
                   async for ev in event_gen(req):
                       try:
                           kind = ev.get("kind") if isinstance(ev, dict) else getattr(ev, "kind", None)
                           if isinstance(kind, str) and len(kind) <= 32:
                               if kind == "error":
                                   saw_error = True  # always tracked, even after preview_truncated
                               elif kind == "done":
                                   saw_done = True
                               elif kind == "delta" and not preview_truncated and not saw_error:
                                   text = ev.get("text") if isinstance(ev, dict) else getattr(ev, "text", None)
                                   if isinstance(text, str) and text:
                                       remaining = MAX_SANITIZE_CHARS - buffered_len
                                       if len(text) > remaining:
                                           preview_parts.append(text[:remaining])
                                           buffered_len = MAX_SANITIZE_CHARS
                                           preview_truncated = True
                                       else:
                                           preview_parts.append(text)
                                           buffered_len += len(text)
                       except Exception:
                           capture_failed = True  # telemetry errors must never disrupt SSE delivery
                       yield _format_sse(ev)  # leave yielded wire frames untouched
                   completed = True
               finally:
                   preview = ""
                   try:
                       preview, preview_truncated = _sanitize_and_bound(
                           "".join(preview_parts),
                           already_truncated=preview_truncated,
                       )
                   except Exception:
                       capture_failed = True
                   has_answer = bool(preview.strip())
                   stream_incomplete = (
                       (not completed)
                       or (not saw_done)
                       or saw_error
                       or capture_failed
                       or (not has_answer)
                   )
                   capture_truncated = input_truncated or preview_truncated
                   if not stream_incomplete and has_answer:
                       try:
                           output_payload: dict[str, object] = {"reply": preview}
                           if preview_truncated:
                               output_payload["truncated"] = True
                           span.set_attribute("output.value", json.dumps(output_payload))
                       except Exception:
                           stream_incomplete = True
                   try:
                       span.set_attribute("neatlogs.capture.truncated", capture_truncated)
                       span.set_attribute("neatlogs.stream.incomplete", stream_incomplete)
                   except Exception:
                       pass
       return StreamingResponse(traced_gen(), media_type="text/event-stream")
   ```

   Wrap the application event generator before SSE wire encoding so completion/error state is authoritative and never depends on parsing raw wire frames; use `StreamingResponse(..., media_type="text/event-stream")` for formatted `str`/`bytes` frames (or `EventSourceResponse` from `sse-starlette` if yielding dict frames).
   - **Approved projections & pre-clip redaction:** Project only allowlisted application fields (`req.message`, `delta` text — ignoring `debug`/internal events and private `metadata`), and sanitize emails, bearer tokens, and API keys *before* clipping to `MAX_PREVIEW_CHARS` (re-bounding after redaction and slicing `text[:remaining]` so multi-megabyte chunks stay bounded).
   - **Fail-open telemetry:** Guard identity lookups (`conversation_id`/`user_id`), input projection, event capture, sanitization, and `span.set_attribute(...)` in `try/except Exception` so telemetry errors never disrupt SSE delivery or alter yielded wire frames.
   - **Authoritative completion & canonical Doctor flags:** Track `completed`, `saw_done`, `saw_error` (even after `preview_truncated`), and `capture_failed` independently of preview buffering; emit `neatlogs.capture.truncated` and `neatlogs.stream.incomplete`, and omit `output.value` unless a nonempty completed answer is known (never publish `{"reply": ""}` or a partial prefix after an error, cancellation, or capture failure).

## Clean Root I/O & Provenance Contract

Automated evaluators and step-by-step replay read the `WORKFLOW` root span first:
- **Non-empty root `input` and `output`:** Ensure the `WORKFLOW` entry point receives the user request and returns the final answer (or explicitly calls `span.set_attribute("input.value", ...)` / `span.set_attribute("output.value", ...)` for streaming handlers or functions that return `None`).
- **Prompt & checkpoint provenance (`neatlogs >= 1.5.0`):** Check installed SDK version first (`python -c "import neatlogs; print(neatlogs.__version__)"`). On `neatlogs >= 1.5.0`, pass `prompt_version="..."` on versioned `WORKFLOW` roots and use `checkpoint_id="..."` (or `neatlogs.checkpoint(...)`) on multi-step loops so traces can be backtracked cleanly (omit on `v1.4.x` to avoid `TypeError`/`AttributeError`). See [`6b-retrievers-and-provenance.md`](6b-retrievers-and-provenance.md).

2. **Does it contain a direct LLM API call?** (client.chat.completions.create, etc.)
   → YES → `@span(kind="CHAIN")` (see Step 5 for trace() wrapper)
   Exception: skip if the function ONLY does `return client.chat.completions.create(...)` with zero other logic.

3. **Does it orchestrate multiple child functions without an LLM call?**
   → YES → `@span(kind="CHAIN")`

4. **Does it do discrete I/O / external API?**
   → YES → `@span(kind="TOOL")` (handled in Step 6)

5. **Is it a pure utility?** (formatting, config, <3 lines, no I/O)
   → NO decorator

## Decorator Placement with Click/Typer

```python
# @neatlogs.span goes BELOW all click decorators, ABOVE def:
@cli.command()
@click.argument("file_path")
@click.option("--output", "-o", default=None)
@neatlogs.span(kind="WORKFLOW", name="process")
def process(file_path: str, output: str | None):
    ...
```

## Decorator Placement with @retry

```python
# @neatlogs.span goes BELOW @retry, closest to def:
@retry(stop=stop_after_attempt(3))
@neatlogs.span(kind="CHAIN", name="summarize_chunk")
async def summarize_chunk(text, settings):
    ...
```

## Action

1. Read ALL source files from the entry point outward.
2. For each CLI command / endpoint / job → add `@span(kind="WORKFLOW")`.
3. For each internal function with an LLM call → add `@span(kind="CHAIN")`.
4. For each internal orchestrator (no LLM, calls children) → add `@span(kind="CHAIN")`.
5. Add `import neatlogs` to each file that gets decorators.

## Verify BEFORE moving to step 5

1. Every CLI command / route handler has `@span(kind="WORKFLOW")`. Count them — if there are 3 commands, there must be 3 WORKFLOW spans.
2. No internal function (run_pipeline, process_document, process_chunk) has kind="WORKFLOW". These are CHAIN.
3. The WORKFLOW span is the outermost decorated function — all other spans are called beneath it.
