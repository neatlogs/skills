# Raw HTTP LLM Calls — TypeScript Manual-Span Reference

When a Node app calls a model API over **raw HTTP** (`fetch` / `undici` / `axios` / `node:https`) instead of a vendor SDK, NeatLogs auto-instrumentation and the provider wrappers (`wrapOpenAI`, `wrapAnthropic`, …) are **blind** — there is no SDK method to patch. You must add a **manual span** and set input / output / token attributes **by hand**, reading them from the raw request/response.

## The two-source rule

1. **Read the app's existing parse code FIRST.** A working raw-HTTP call already pulls text/tokens out of the response JSON. Tap the SAME values into span attributes — that's the ground truth, no external knowledge needed.
2. **Use the wire-format field paths as a fallback** when the code parses loosely. **The HTTP request/response JSON shapes are identical to the Python reference** — see `neatlogs-py-setup/references/raw-http-llm-formats.md` for the per-provider paths (OpenAI Chat + Responses, Anthropic, Gemini Vertex + AI Studio; streaming + non-streaming; the token-location gotchas). The wire is language-agnostic; only the SDK API below differs.

**Sync/async is irrelevant** — it's just HTTP. Same JSON, same field paths.

## Detect the provider from the request URL

| URL contains | Provider | Wire format |
|---|---|---|
| `api.openai.com/v1/chat/completions`, `*.openai.azure.com/...`, Groq/Together | OpenAI Chat (-compatible) | §A in the Python ref |
| `api.openai.com/v1/responses` | OpenAI Responses | §B |
| `api.anthropic.com/v1/messages` | Anthropic | §C |
| `generativelanguage.googleapis.com/...:generateContent`, `*-aiplatform.googleapis.com/...:generateContent`, `:streamGenerateContent` | Gemini (AI Studio / Vertex) | §D |

## Canonical attribute names

Set the canonical `neatlogs.*` names exactly — the backend only renders keys it recognizes. Unlike the Python SDK (which ships `config/attribute-mapping.json` as a readable file), the **TypeScript SDK inlines the mapping into its bundled JS**, so there is no file to open at runtime. The authoritative names are listed here:

| Purpose | Attribute |
|---|---|
| span kind | `neatlogs.span.kind` (set `'LLM'`; or set `openinference.span.kind='LLM'` on a raw OTel span — see streaming below) |
| dashboard visibility | `neatlogs.internal` → **`false`** on a manual LLM span with no auto-instrumented sibling (else the backend drops it) |
| model | `neatlogs.llm.model_name` |
| provider | `neatlogs.llm.provider` |
| input (whole) | `neatlogs.llm.input` — JSON `{"messages":[...]}` |
| input (indexed) | `neatlogs.llm.input_messages.{i}.role` / `.content` |
| output (whole) | `neatlogs.llm.output` — JSON `{"role":"assistant","content":...}` |
| output (indexed) | `neatlogs.llm.output_messages.{i}.role` / `.content` |
| tokens | `neatlogs.llm.token_count.{prompt,completion,total,cache_read,cache_write,reasoning}` |
| finish/stop | `neatlogs.llm.finish_reason` / `neatlogs.llm.stop_reason` |
| tool span | `neatlogs.tool.{name,description,id,parameters}` |

(These match the Python SDK's `config/attribute-mapping.json` one-for-one. If you need a key not listed, check `neatlogs-py-setup/references/llm-call-patterns.md` "Authoritative attribute names" — the canonical set is shared across both SDKs.)

---

## Non-streaming → use the `trace()` callback

`trace(opts, async (span) => {...})` opens the span, runs the callback, and closes it when the callback returns. Perfect for a single awaited request:

```typescript
import { trace } from 'neatlogs';

async function rawGeminiCall(model: string, inputMessages: any[], payload: object, url: string, headers: Record<string,string>) {
  return await trace({ name: 'Gemini generate', kind: 'LLM' }, async (span) => {
    span.setAttribute('neatlogs.internal', false);
    span.setAttribute('neatlogs.llm.model_name', model);
    span.setAttribute('neatlogs.llm.input', JSON.stringify({ messages: inputMessages }));

    const resp = await fetch(url, { method: 'POST', headers, body: JSON.stringify(payload) });
    const data = await resp.json();

    // Field paths per provider — see the Python wire-format ref (§A–§D).
    const text = data.candidates?.[0]?.content?.parts?.map((p: any) => p.text).filter(Boolean).join('') ?? '';
    span.setAttribute('neatlogs.llm.output', JSON.stringify({ role: 'assistant', content: text }));

    const u = data.usageMetadata ?? {};
    span.setAttribute('neatlogs.llm.token_count.prompt', u.promptTokenCount ?? 0);
    span.setAttribute('neatlogs.llm.token_count.completion', u.candidatesTokenCount ?? 0);
    span.setAttribute('neatlogs.llm.token_count.total', u.totalTokenCount ?? 0);
    return data;
  });
}
```

---

## Streaming → `trace()` CANNOT bracket a stream; use raw OTel start/end

The `trace()` callback closes its span the moment the callback returns. A streaming response is an **async iterator that yields to the consumer over time** — you must keep the span open across yields and close it at a precise point. Use the underlying OpenTelemetry tracer directly (the same one `trace()` uses) so you control `startSpan()` / `end()` explicitly — the TS equivalent of Python's `__enter__` / `__exit__`.

```typescript
import { trace as otelTrace, SpanStatusCode } from '@opentelemetry/api';

async function* streamGemini(model: string, inputMessages: any[], payload: object, url: string, headers: Record<string,string>) {
  const tracer = otelTrace.getTracer('neatlogs.trace');

  // 1. Open the LLM span BEFORE the stream; set INPUT now.
  const span = tracer.startSpan('Gemini generate');
  span.setAttribute('neatlogs.internal', false);
  span.setAttribute('openinference.span.kind', 'LLM');  // what trace() sets internally
  span.setAttribute('neatlogs.llm.model_name', model);
  span.setAttribute('neatlogs.llm.input', JSON.stringify({ messages: inputMessages }));

  let textParts: string[] = [];
  let prompt = 0, completion = 0, total = 0;
  let finished = false, spanEnded = false;

  try {
    const resp = await fetch(`${url}?alt=sse`, { method: 'POST', headers, body: JSON.stringify(payload) });
    const reader = resp.body!.getReader();
    const decoder = new TextDecoder();
    let buf = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      const lines = buf.split('\n');
      buf = lines.pop() ?? '';
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        const chunk = JSON.parse(line.slice(6));

        // 2. Accumulate text + tokens across chunks (paths per provider).
        const t = chunk.candidates?.[0]?.content?.parts?.map((p: any) => p.text).filter(Boolean).join('');
        if (t) { textParts.push(t); yield t; }
        if (chunk.usageMetadata) {       // last chunk carries cumulative usage — don't sum
          prompt = chunk.usageMetadata.promptTokenCount ?? prompt;
          completion = chunk.usageMetadata.candidatesTokenCount ?? completion;
          total = chunk.usageMetadata.totalTokenCount ?? total;
        }

        if (chunk.candidates?.[0]?.finishReason) {
          finished = true;
          // 3. Attach OUTPUT + TOKENS once the stream is complete.
          span.setAttribute('neatlogs.llm.output', JSON.stringify({ role: 'assistant', content: textParts.join('') }));
          span.setAttribute('neatlogs.llm.token_count.prompt', prompt);
          span.setAttribute('neatlogs.llm.token_count.completion', completion);
          span.setAttribute('neatlogs.llm.token_count.total', total);
          // 4. End the span BEFORE the final yield (see WHY below).
          span.end();
          spanEnded = true;
        }
      }
    }
  } catch (err) {
    span.setStatus({ code: SpanStatusCode.ERROR, message: err instanceof Error ? err.message : String(err) });
    throw err;
  } finally {
    // 5. Double-end guard: close exactly once whether the stream finished,
    //    errored, or the consumer abandoned the generator.
    if (!finished) {
      span.setAttribute('neatlogs.llm.output', JSON.stringify({ role: 'assistant', content: textParts.join('') }));
    }
    if (!spanEnded) span.end();
  }
}
```

### The two rules that are easy to get wrong (same as Python)

1. **`end()` before the consumer's next operation, not only in `finally`.** A generator hands control back on every `yield`. If the span is still open (active) when the consumer starts its next operation, that operation nests as a CHILD of this LLM span instead of a sibling — a wrong trace tree. End it before the terminal work. The `spanEnded` flag keeps `finally` from double-ending.

2. **`end()` exactly once.** A generator can exit by completion, exception, or abandonment (the consumer stops iterating). The `finally` + `spanEnded` guard closes it once in all three. Double `end()` on an OTel span is a bug.

> Note: raw `startSpan()` does NOT auto-nest under the current active span the way `trace()` does. If this streaming call must nest under a parent span, start it within the parent's context: `otelContext.with(otelTrace.setSpan(otelContext.active(), parentSpan), () => tracer.startSpan(...))`, or open it inside the parent `trace()`/`span()` scope.
