# Raw HTTP LLM Provider Wire Formats — Manual-Span Reference

When an app calls a model API over **raw HTTP** (`httpx` / `requests` / `aiohttp`) instead of the vendor SDK, `neatlogs.wrap()` and ALL auto-instrumentation are **blind** — there is no SDK method to patch. You must add a **manual span** and set input / output / token attributes **by hand**, reading them out of the raw request and response.

## How to instrument a raw-HTTP LLM call (the two-source rule)

1. **Read the existing parse code FIRST.** A working raw-HTTP call already extracts what it needs (text, sometimes tokens) from the response — e.g. `data["usageMetadata"]["totalTokenCount"]`. Tap the SAME variables into span attributes. This is the ground truth and needs no external knowledge.
2. **Use the tables below as the fallback** when the code parses loosely (e.g. only pulls text, never reads usage) — then you know where the tokens *would* be. These formats are stable and identical across all users; they're baked in here so this works with no internet access.

Set the canonical `neatlogs.*` attribute names (verify against the SDK file — see `llm-call-patterns.md` "Authoritative attribute names"). Core ones:
`neatlogs.llm.model_name`, `neatlogs.llm.input` (JSON `{"messages":[...]}`), `neatlogs.llm.output` (JSON `{"role":"assistant","content":...}`), `neatlogs.llm.token_count.{prompt,completion,total,cache_read,reasoning}`.

**Sync vs async is identical bytes.** Raw HTTP is just HTTP — `requests` vs `aiohttp`, `httpx.Client` vs `httpx.AsyncClient` only changes how you await/iterate the socket, NOT the request/response JSON or the field paths. One extraction logic serves both.

---

## How to detect which provider a raw HTTP call targets

Match on the **URL** in the `.post(...)` / `.stream("POST", ...)`:

| URL contains | Provider | Format below |
|---|---|---|
| `api.openai.com/v1/chat/completions` | OpenAI Chat Completions | §A |
| `api.openai.com/v1/responses` | OpenAI Responses | §B |
| `*.openai.azure.com/.../chat/completions` | Azure OpenAI | §A (same shape) |
| `api.anthropic.com/v1/messages` | Anthropic Messages | §C |
| `generativelanguage.googleapis.com/.../:generateContent` | Google AI Studio (Gemini) | §D |
| `*-aiplatform.googleapis.com/.../:generateContent` | Vertex AI (Gemini) | §D |
| `...:streamGenerateContent` | Gemini (streaming) | §D |
| `api.groq.com`, `api.together.xyz`, Mistral, etc. | OpenAI-compatible | §A (same shape) |

---

## §A. OpenAI Chat Completions (`POST /v1/chat/completions`)

Also covers Azure OpenAI, Groq, Together, and other OpenAI-compatible endpoints — identical shape.

### Request
- Input messages: **`body["messages"]`** → `[{role, content}]`
- Model: **`body["model"]`**
- Streaming: `body["stream"] = true`. **To get usage in a stream you MUST send `body["stream_options"] = {"include_usage": true}`** — otherwise usage is never emitted.

### Non-streaming response
| Attribute | Path in response JSON |
|---|---|
| output text | `choices[0]["message"]["content"]` |
| tool calls | `choices[0]["message"]["tool_calls"]` → each `{id, type, function:{name, arguments}}` (`arguments` is a JSON **string**) |
| finish reason | `choices[0]["finish_reason"]` |
| prompt tokens | `usage["prompt_tokens"]` |
| completion tokens | `usage["completion_tokens"]` |
| total tokens | `usage["total_tokens"]` |
| reasoning tokens (opt) | `usage["completion_tokens_details"]["reasoning_tokens"]` |
| cached tokens (opt) | `usage["prompt_tokens_details"]["cached_tokens"]` |

### Streaming (SSE)
- Lines: `data: {chunk}\n\n`, terminated by literal `data: [DONE]`.
- Incremental text: **`choices[0]["delta"]["content"]`** (accumulate across chunks).
- Tool calls stream at `choices[0]["delta"]["tool_calls"]` with an `index` to reassemble; concat `function.arguments`.
- **Tokens:** only with `stream_options.include_usage=true`. A FINAL chunk (just before `[DONE]`) has **`choices: []`** and a top-level **`usage`** object (same shape as non-streaming). All earlier chunks have `usage: null`. → Read `usage` from the chunk whose `choices` is empty.

```python
# streaming accumulation sketch (sync or async — same parsing)
text_parts, usage = [], None
# for line in resp.iter_lines():  /  async for line in resp.aiter_lines():
    if not line.startswith("data: "): continue
    body = line[6:]
    if body == "[DONE]": break
    chunk = json.loads(body)
    if chunk["choices"]:
        delta = chunk["choices"][0]["delta"]
        if delta.get("content"): text_parts.append(delta["content"])
    elif chunk.get("usage"):
        usage = chunk["usage"]   # final usage chunk: choices == []
```

---

## §B. OpenAI Responses API (`POST /v1/responses`)

### Request
- Input: **`body["input"]`** — a string OR `[{role, content}]`.
- Streaming: `body["stream"] = true`. **No `include_usage` flag** — usage always arrives on the terminal event.

### Non-streaming response
- Output is an **array** `output[]`. Assistant text: iterate `output[]` where `type == "message"`, then its `content[]` where `type == "output_text"`, take `["text"]`.
- Tool/function calls are their own `output[]` items (`type == "function_call"`, with `name`/`arguments`/`call_id`).
- Status (not finish_reason): top-level `status`.
- **Tokens (note the different names vs Chat):** `usage["input_tokens"]`, `usage["output_tokens"]`, `usage["total_tokens"]`, `usage["input_tokens_details"]["cached_tokens"]`, `usage["output_tokens_details"]["reasoning_tokens"]`.

### Streaming (typed semantic SSE events)
- Each `data:` line has a `type`. Text deltas: events with `type == "response.output_text.delta"`, fragment in **`["delta"]`** (a plain string).
- **Tokens:** on the terminal **`response.completed`** event at **`event["response"]["usage"]`** (full Response object with `input_tokens`/`output_tokens`/`total_tokens`). Key off the `response.completed` (and `error`) event type to detect end-of-stream — there is no `[DONE]` sentinel.

---

## §C. Anthropic Messages (`POST /v1/messages`)

Required header: `anthropic-version: 2023-06-01`.

### Request
- **`body["system"]`** is the system prompt — a TOP-LEVEL field (string OR `[{type:"text", text}]`), NOT a message. Capture it separately when building `neatlogs.llm.input`.
- **`body["messages"]`** → `[{role, content}]`, role is `user`/`assistant`. `content` is a string OR an array of blocks — handle both.
- Streaming: `body["stream"] = true`.

### Non-streaming response
`content` is **always an array of blocks** — iterate and switch on `type`; do not assume `content[0]` is text.
| Attribute | Path |
|---|---|
| output text | first block where `content[i]["type"]=="text"` → `content[i]["text"]` |
| tool call | block where `type=="tool_use"` → `name`, `input` (object), `id` |
| stop reason | `stop_reason` |
| input tokens | `usage["input_tokens"]` |
| output tokens | `usage["output_tokens"]` |
| cache write | `usage["cache_creation_input_tokens"]` |
| cache read | `usage["cache_read_input_tokens"]` |

### Streaming (named SSE events) — THE GOTCHA: tokens are split across two events
Event flow: `message_start` → (`content_block_start` → `content_block_delta`… → `content_block_stop`)* → `message_delta`* → `message_stop` (plus `ping`/`error`).

- **`message_start`** → input tokens land HERE: `data["message"]["usage"]["input_tokens"]` (+ `cache_creation_input_tokens`, `cache_read_input_tokens`). The `output_tokens` here is a tiny placeholder — ignore it.
- **`content_block_delta`** → text: when `data["delta"]["type"]=="text_delta"`, append `data["delta"]["text"]`. Tool input: when `type=="input_json_delta"`, concat `data["delta"]["partial_json"]` then `json.loads` once the block stops.
- **`message_delta`** → output tokens + stop reason land HERE: `data["usage"]["output_tokens"]` and `data["delta"]["stop_reason"]`. **Counts are CUMULATIVE — take the LAST `message_delta`, do not sum.**

⚠️ You MUST capture both `message_start` (input) and the final `message_delta` (output) to get a complete token count. Reading only one gives you half.

```python
in_tok = out_tok = 0; text_parts = []
# for evt in sse_events(resp):  (sync or async — same)
    d = json.loads(evt.data)
    t = d.get("type")
    if t == "message_start":
        in_tok = d["message"]["usage"]["input_tokens"]
    elif t == "content_block_delta" and d["delta"].get("type") == "text_delta":
        text_parts.append(d["delta"]["text"])
    elif t == "message_delta":
        out_tok = d["usage"]["output_tokens"]   # cumulative; last one wins
```

---

## §D. Google Gemini (`:generateContent` / `:streamGenerateContent`)

Same JSON shapes for **AI Studio** (`generativelanguage.googleapis.com/v1beta`) and **Vertex AI** (`*-aiplatform.googleapis.com/v1`) — only host/path/version/auth differ.

### Request
- Input: **`body["contents"]`** → `[{role, parts:[{text}]}]`. Role is **`"user"`/`"model"`** (NOT `"assistant"`).
- System prompt: **`body["systemInstruction"]["parts"][].text`** (separate field).
- Tool results are a `functionResponse` part inside a `contents` entry (conventionally `role:"user"`), not a separate role.

### Non-streaming response (`:generateContent`)
`parts` is an **array** — text may be split; concatenate `text` over all parts that have it.
| Attribute | Path |
|---|---|
| output text | join `candidates[0]["content"]["parts"][i]["text"]` for parts with `text` (skip parts where `thought==true` or only `functionCall`/`thoughtSignature`) |
| function call | `candidates[0]["content"]["parts"][i]["functionCall"]` → `name`, `args` |
| finish reason | `candidates[0]["finishReason"]` (`STOP`, `MAX_TOKENS`, `SAFETY`, …) |
| prompt tokens | `usageMetadata["promptTokenCount"]` |
| completion tokens | `usageMetadata["candidatesTokenCount"]` |
| total tokens | `usageMetadata["totalTokenCount"]` |
| reasoning tokens (thinking models) | `usageMetadata["thoughtsTokenCount"]` → map to `neatlogs.llm.token_count.reasoning` |

### Streaming (`:streamGenerateContent`) — two framings
- **Default (no `?alt=sse`):** the body is one big JSON **array** of `GenerateContentResponse` objects, flushed incrementally (bracket-balance to parse mid-stream, or `json.loads` whole at end).
- **With `?alt=sse`:** SSE — each chunk is `data: {GenerateContentResponse}`; strip the `data: ` prefix and parse.
- Incremental text: same path — `candidates[0]["content"]["parts"][].text` — each chunk carries a fragment; concatenate in order.
- **Tokens:** `usageMetadata` rides on chunks; the **FINAL chunk** (the one with `finishReason`) carries the cumulative `usageMetadata` with the complete counts. **Do NOT sum `usageMetadata` across chunks** — take the last one that has it.
- Gemini 3.x: `candidates[].content.parts[].thoughtSignature` (top-level on a Part) — opaque, skip for output text; `part["thought"]==true` marks reasoning parts to exclude from the answer.

---

## Streaming lifecycle for manual spans (all providers)

A streaming raw-HTTP call needs careful span lifecycle — see `raw-http-streaming-span.md` for the full pattern (manual `__enter__`/`__exit__`, accumulate-in-loop, close-before-final-yield to keep trace nesting correct, and the `finally` double-close guard).
