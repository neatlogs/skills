# Manual Span Lifecycle for Streaming Raw-HTTP LLM Calls

A streaming raw-HTTP LLM call (`httpx`/`requests`/`aiohttp` over an async generator) needs the span to:
1. open **before** the stream starts (to capture input),
2. **accumulate output text + tokens across chunks** — THIS IS THE STEP MOST OFTEN MISSED. Yielding a chunk to the caller does NOT record it on the span; you must append each chunk's text to a local list yourself,
3. attach output/token attributes (`neatlogs.llm.output`, token counts) **before the span closes** — a span with only input is lossy (shows the prompt, not the completion),
4. close at the right moment so the trace tree nests correctly,
5. close **exactly once** whether the generator finishes, errors, or is abandoned.

A `with neatlogs.trace(...) as span:` block is PERFECTLY FINE for a streaming async generator — a `with` inside an async generator stays open across `yield`s (the generator frame suspends, it doesn't exit). Use `with` when you can; only drop to the manual `__enter__()`/`__exit__()` form when you must close the span BEFORE the final `yield` for correct sibling nesting (case below). Either way, step 2 (accumulate) + step 3 (set output before close) are MANDATORY. Read `raw-http-llm-formats.md` for the per-provider field paths used below.

## Full pattern (async streaming generator)

```python
import json
import neatlogs

async def stream_completion(self, model, system_prompt, contents, payload, url, headers):
    client = get_raw_api_client()
    accumulated_text: list[str] = []
    prompt_tokens = completion_tokens = total_tokens = 0
    finished = False

    # 1. Open the LLM span BEFORE the stream and set INPUT now.
    trace_cm = neatlogs.trace("Gemini generate", kind="LLM")
    span = trace_cm.__enter__()
    span_closed = False
    try:
        span.set_attribute("neatlogs.llm.model_name", model)
        input_messages = build_input_messages(system_prompt, contents)  # your existing shaping
        span.set_attribute("neatlogs.llm.input", json.dumps({"messages": input_messages}))

        async with client.stream("POST", url, json=payload, headers=headers) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                chunk = json.loads(line[6:])

                # 2. Accumulate output text + tokens across chunks
                #    (use the provider's field paths from raw-http-llm-formats.md)
                part_text = extract_chunk_text(chunk)
                if part_text:
                    accumulated_text.append(part_text)
                    yield StreamChunk(type=TEXT, text=part_text)

                usage = extract_chunk_usage(chunk)   # last chunk carries cumulative usage
                if usage:
                    prompt_tokens = usage.get("promptTokenCount", prompt_tokens)
                    completion_tokens = usage.get("candidatesTokenCount", completion_tokens)
                    total_tokens = usage.get("totalTokenCount", total_tokens)

                if chunk_is_final(chunk):            # e.g. has finishReason / choices==[] / [DONE]
                    finished = True
                    # 3. Attach OUTPUT + TOKENS now that the stream is complete.
                    span.set_attribute(
                        "neatlogs.llm.output",
                        json.dumps({"role": "assistant", "content": "".join(accumulated_text)}),
                    )
                    span.set_attribute("neatlogs.llm.token_count.prompt", prompt_tokens)
                    span.set_attribute("neatlogs.llm.token_count.completion", completion_tokens)
                    span.set_attribute("neatlogs.llm.token_count.total", total_tokens)

                    # 4. Close the LLM span BEFORE yielding the FINAL chunk.
                    #    WHY: the consumer (e.g. an agent loop) starts its NEXT
                    #    operation the instant it receives FINISH. If the span is
                    #    still open on the OTel context then, that next operation
                    #    nests as a CHILD of this LLM span instead of a sibling —
                    #    a wrong trace tree. Closing here fixes the nesting.
                    trace_cm.__exit__(None, None, None)
                    span_closed = True
                    yield StreamChunk(type=FINISH)
    finally:
        # 5. Double-close guard: if the stream errored or was abandoned before
        #    the final chunk, attach what we have and close exactly once.
        if not finished:
            span.set_attribute(
                "neatlogs.llm.output",
                json.dumps({"role": "assistant", "content": "".join(accumulated_text)}),
            )
        if not span_closed:
            trace_cm.__exit__(None, None, None)
```

## The two rules that are easy to get wrong

1. **Close before the final yield, not in `finally`.** A streaming generator hands control back to its consumer on every `yield`. If you let `finally` close the span, the consumer has already started the next operation while this span is still active → it renders as a child of the LLM. Close it *before* `yield FINISH` for correct sibling nesting. Use a `span_closed` flag so `finally` doesn't double-close.

2. **`__exit__` exactly once.** A generator can exit three ways: normal completion (final chunk), exception, or the consumer abandoning it (GeneratorExit). The `finally` + `span_closed` guard ensures the span closes once in all three — double `__exit__()` on an OTel span is a bug.

3. **The span is the RETURN of `__enter__()`, not the trace() object.** `neatlogs.trace(...)` returns a *context manager* (`_GeneratorContextManager`), not a span. You MUST bind two distinct names: `trace_cm = neatlogs.trace(...)` then `span = trace_cm.__enter__()`. Call `span.set_attribute(...)` on the span and `trace_cm.__exit__(...)` on the context manager. The common mistake `s = neatlogs.trace(...); s.__enter__(); s.set_attribute(...)` raises `'_GeneratorContextManager' object has no attribute 'set_attribute'` — because `s` is the context manager and the span (the `__enter__()` return) was thrown away.

## Non-streaming raw-HTTP is simpler — use a plain `with`

If the call isn't streamed, a normal context manager is fine (no early-close needed):

```python
with neatlogs.trace("Gemini generate", kind="LLM") as span:
    span.set_attribute("neatlogs.llm.model_name", model)
    span.set_attribute("neatlogs.llm.input", json.dumps({"messages": input_messages}))
    resp = await client.post(url, json=payload, headers=headers)
    data = resp.json()
    span.set_attribute("neatlogs.llm.output", json.dumps({"role": "assistant", "content": output_text}))
    span.set_attribute("neatlogs.llm.token_count.prompt", data["usageMetadata"]["promptTokenCount"])
    span.set_attribute("neatlogs.llm.token_count.completion", data["usageMetadata"]["candidatesTokenCount"])
    span.set_attribute("neatlogs.llm.token_count.total", data["usageMetadata"]["totalTokenCount"])
```
