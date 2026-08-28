# Troubleshooting — NeatLogs TypeScript SDK Reference

Common mistakes, anti-patterns, and diagnostic steps for the NeatLogs TypeScript SDK.

---

## 1. `instrumentations: [...]` Throws (Most Common Mistake)

`init()` **rejects** every provider/framework instrumentation key — the underlying OpenInference/OTel-contrib instrumentors drive the **global** OTel context, which Neatlogs' private provider cannot isolate. The thrown error names the replacement helper.

```typescript
// Supported: per-instance wrapper; import order is irrelevant
import { OpenAI } from 'openai';
import { init, wrapOpenAI } from 'neatlogs';
await init({ apiKey: process.env.NEATLOGS_API_KEY });
const client = wrapOpenAI(new OpenAI());
```

Do not publish or generate a copyable `instrumentations` initialization snippet,
even as a negative example. State the incompatibility in prose and show only the
supported wrapper or hook.

Because the helpers patch the **instance** you pass (not the module), there is **no import-order rule** in the TypeScript SDK and no need for dynamic `import()`. See the [core mechanism](../SKILL.md#core-mechanism-different-from-other-skills) for the helper for each library.

---

## 2. Forgetting to Await Lifecycle Functions

`init()`, `flush()`, and `shutdown()` are all async and MUST be awaited.

```typescript
// ❌ WRONG — not awaiting
init({ apiKey: '...' });  // Returns a Promise that's never awaited

// ✅ RIGHT
await init({ apiKey: '...' });
```

```typescript
// ❌ WRONG — not awaiting shutdown
flush();
shutdown();

// ✅ RIGHT
await flush();
await shutdown();
```

---

## 3. Missing Traces Diagnostic Flowchart

If traces are not appearing in the NeatLogs dashboard, check these in order:

1. **Is `await init()` called?** → No → Add `await init(...)` at the top of your entry file.
2. **Did `init()` throw?** → An `instrumentations: [...]` key in `init()` throws — remove it (see §1).
3. **Is the client actually wrapped?** → No → Apply the matching helper from the [core mechanism](../SKILL.md#core-mechanism-different-from-other-skills), e.g. `const client = wrapOpenAI(new OpenAI())`. Wrapping the *return value* and then calling the **original** variable is the usual slip.
4. **Is `NEATLOGS_API_KEY` set?** → No → Set it via env var or `apiKey` param. Without it, export is **silently disabled**.
5. **Does a helper exist for this library?** → Check the [core mechanism](../SKILL.md#core-mechanism-different-from-other-skills). If not, the calls are raw HTTP as far as Neatlogs is concerned → add manual spans (see [`raw-http-llm.md`](raw-http-llm.md)).
6. **Still missing?** → Enable `debug: true` in `init()` and check console output for clues.

---

## 4. HTTP Auto-Instrumentation (Always On)

`init()` **always** instruments Node.js `fetch`/`undici` for trace context propagation. There is nothing to configure.

---

## 5. Flush/Shutdown Gotcha

Scripts (not long-running servers) **MUST** call `await flush()` then `await shutdown()` before exit. Without them, the last batch of spans may not be exported.

```typescript
// At the end of your script
await flush();
await shutdown();
```

### Long-Running Servers

For servers, call `init()` **once at startup** and `flush()` / `shutdown()` **once at shutdown** — NOT on every request:

```typescript
// ❌ WRONG — flush on every request
app.get('/ask', async (req, res) => {
  const response = await client.chat.completions.create({ /* ... */ });
  await flush();    // ← Don't do this per request
  res.json({ answer: response.choices[0].message.content });
});

// ✅ RIGHT — flush only on shutdown
process.on('SIGTERM', async () => {
  await flush();
  await shutdown();
  process.exit(0);
});
```

**Why?** `flush()` on every request sends one HTTP batch per request instead of one every `flushInterval` seconds (default 5s) — this risks API throttling and adds latency.

---

## 6. No-Op Instrumentation Keys

`litellm`, `crewai`, `cohere`, `groq`, `llamaindex` and the vector-DB keys are in the registry but load no instrumentor, so `init()` accepts them **without throwing** — and instruments nothing. They're Python-side entries kept for scope detection; passing them buys you nothing and hides the fact that those calls are untraced.

Use the [core mechanism](../SKILL.md#core-mechanism-different-from-other-skills) as the source of truth. For a library with no helper, instrument the call sites manually — see [`raw-http-llm.md`](raw-http-llm.md).

---

## 7. Debug Mode

```typescript
await init({ debug: true });
```

- Enables verbose logging to console (instrumentation status, span creation, export status)
- Enables `log()` echo to console
- Shows endpoint configuration, provider/exporter setup, etc.

---

## 8. Common Anti-Patterns Table

| Anti-Pattern | Why It's Wrong | Fix |
|-------------|----------------|-----|
| Wrapping `span({ kind: 'WORKFLOW' })` in `trace()` | Redundant — `span()` already creates a span | Just call the wrapped function directly |
| Using `trace()` for custom functions where `span()` would work | That's what `span()` is for | Use `span({ kind: 'CHAIN' })` or the appropriate kind |
| Passing `instrumentations: ['openai']` (or any provider/framework key) | `init()` **throws** | Remove the key; use `wrapOpenAI(client)` etc. |
| Leaving a client unwrapped | Its LLM calls won't be traced | Apply the helper to every provider client your code constructs |
| Using `span({ kind: 'RERANKER' })` or `span({ kind: 'VECTOR_STORE' })` | `span()` throws Error for invalid kinds | Below an eligible root, use `trace({ name: '...', kind: 'RERANKER' as any })`; the cast is required by the current narrow type declaration |
| Using dynamic `import()` "so instrumentation applies" | Pointless — helpers patch instances, not modules | Use a plain static `import` |
| Using `span({ kind: 'LLM' })` | `LLM` is not a valid kind for `span()` | For an unsupported/raw call below an eligible root only, use `trace({ name: '...', kind: 'LLM' as any })`; otherwise use the supported wrapper/integration |

---

## 9. Manual `trace({ kind: 'LLM' })` Span Disappears From Dashboard

**Symptom**: A chat/agent step shows its parent AGENT span with no children in the UI.

This section applies only to a raw HTTP or unsupported SDK call with no wrapper,
handler, hook, processor, or instrumentor. Automatically captured calls must
not get another manual LLM trace.

**Root cause**: `trace()` stamps `neatlogs.internal = true` on every span by default. The backend drops internal LLM spans when it expects an auto-instrumented sibling.

**Fix**: Opt out of the internal flag inside the callback:

```typescript
await trace({ name: 'raw_api_request', kind: 'WORKFLOW' }, async () =>
  trace({ name: 'raw_api_llm_call', kind: 'LLM' as any }, async (span) => {
    span.setAttribute('neatlogs.internal', false);   // required
    // ... canonical input/model, API call, output/usage/error writes ...
  }),
);
```

If a real eligible `WORKFLOW`, `CHAIN`, `AGENT`, or `MCP_TOOL` parent is already active, reuse it instead of adding the example root. A manual `LLM` cannot finalize as a parentless root.

> Do NOT override `neatlogs.internal = false` on a `trace()` that wraps a call a `wrap*` helper already traces. The wrapper's own LLM span IS the canonical record — leaving the internal flag in place correctly removes the redundant outer span.

---

## 10. Data Masking

Per-span mask override:

```typescript
import { span } from 'neatlogs';
import type { MaskFunction } from 'neatlogs';

const redactPii: MaskFunction = (spanData) => {
  for (const key of Object.keys(spanData)) {
    if (key.includes('email') || key.includes('password')) {
      spanData[key] = '[REDACTED]';
    }
  }
  return spanData;
};

const lookupUser = span(
  { kind: 'TOOL', toolName: 'lookup_user', mask: redactPii },
  async (email: string) => {
    return await db.findUser(email);
  },
);
```

> **Note**: Per-span mask takes precedence — the global `init({ mask })` mask is skipped for that span.

---

## 11. NEATLOGS_TRACE_CONTENT Environment Variable

Set `NEATLOGS_TRACE_CONTENT=false` to globally disable input/output capture on all spans (overrides `captureInput`/`captureOutput` defaults). Useful for production environments with sensitive data.

```bash
export NEATLOGS_TRACE_CONTENT=false
```

---

## 12. Next.js: `Module not found: Can't resolve 'crypto'` (500, no traces)

**Symptom:** the Next.js server fails to compile/serve with `Module not found: Can't resolve 'crypto'`, with the import trace pointing at `./src/instrumentation.ts`. The route returns HTTP 500 and no spans are emitted.

**Cause:** a STATIC top-level `import { init } from "neatlogs"` in `instrumentation.ts` makes Next's instrumentation-layer bundler statically analyze the Node-only SDK (which uses `crypto`) and fail. `serverExternalPackages` does NOT cover the `instrumentation.ts` compilation.

**Fix:** import `neatlogs` dynamically INSIDE `register()`:

```typescript
// src/instrumentation.ts
export async function register() {
  if (process.env.NEXT_RUNTIME === "nodejs") {
    const { init } = await import("neatlogs");   // ✅ dynamic, not top-level
    await init({ apiKey: process.env.NEATLOGS_API_KEY ?? "", workflowName: "my-next-app" });
  }
}
```

This is what the `gemini-chatbot` example does. If a specific ROUTE (not instrumentation.ts) still errors, add `serverExternalPackages: ["neatlogs"]` to `next.config` as a fallback. See `references/nextjs.md`.
