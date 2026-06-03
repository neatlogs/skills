# LLM Call Patterns — How to Recognize Them

Every LLM call in the project needs `with neatlogs.trace("<name>", kind="LLM")` + prompt templates, regardless of whether the containing function has `@span` (`name` is the required first positional arg). Use this reference to identify LLM calls across all supported libraries.

## OpenAI SDK (`openai`)

```python
# Sync
client = OpenAI()
response = client.chat.completions.create(model="gpt-4o", messages=[...])

# Async
client = AsyncOpenAI()
response = await client.chat.completions.create(model="gpt-4o", messages=[...])

# Streaming
stream = client.chat.completions.create(model="gpt-4o", messages=[...], stream=True)
for chunk in stream: ...

# Async streaming
stream = await client.chat.completions.create(model="gpt-4o", messages=[...], stream=True)
async for chunk in stream: ...

# Responses API
response = client.responses.create(model="gpt-4o", input="...")
```

**Pattern to match:** `*.chat.completions.create(` or `*.responses.create(`

## Anthropic SDK (`anthropic`)

```python
# Sync
client = Anthropic()
message = client.messages.create(model="claude-sonnet-4-20250514", messages=[...], max_tokens=1024)

# Async
client = AsyncAnthropic()
message = await client.messages.create(model="claude-sonnet-4-20250514", messages=[...], max_tokens=1024)

# Streaming
with client.messages.stream(model="claude-sonnet-4-20250514", messages=[...]) as stream:
    for text in stream.text_stream: ...

# Async streaming
async with client.messages.stream(model="claude-sonnet-4-20250514", messages=[...]) as stream:
    async for text in stream.text_stream: ...
```

**Pattern to match:** `*.messages.create(` or `*.messages.stream(`

## Google GenAI (`google-genai`)

```python
from google import genai

client = genai.Client()
response = client.models.generate_content(model="gemini-2.0-flash", contents="...")

# Streaming
for chunk in client.models.generate_content_stream(model="gemini-2.0-flash", contents="..."):
    ...

# Async
response = await client.aio.models.generate_content(model="gemini-2.0-flash", contents="...")
```

**Pattern to match:** `*.models.generate_content(` or `*.models.generate_content_stream(` or `*.aio.models.generate_content(`

## LangChain (`langchain-openai`, `langchain-anthropic`, etc.)

```python
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic

llm = ChatOpenAI(model="gpt-4o")
llm = ChatAnthropic(model="claude-sonnet-4-20250514")

# Invoke (sync)
response = llm.invoke(messages)
response = llm.invoke("prompt string")

# Async invoke
response = await llm.ainvoke(messages)

# Streaming
for chunk in llm.stream(messages): ...
async for chunk in llm.astream(messages): ...

# With tool binding
llm_with_tools = llm.bind_tools([...])
response = llm_with_tools.invoke(messages)
```

**Pattern to match:** `llm.invoke(`, `llm.ainvoke(`, `llm.stream(`, `llm.astream(`, `llm_with_tools.invoke(`

## Groq SDK (`groq`)

```python
from groq import Groq, AsyncGroq

client = Groq()
response = client.chat.completions.create(model="llama-3.3-70b", messages=[...])

# Async
client = AsyncGroq()
response = await client.chat.completions.create(model="llama-3.3-70b", messages=[...])
```

**Pattern to match:** same as OpenAI — `*.chat.completions.create(`

## Cohere SDK (`cohere`)

```python
import cohere

client = cohere.Client()
response = client.chat(message="...", model="command-r-plus")

# v2
response = client.v2.chat(model="command-r-plus", messages=[...])
```

**Pattern to match:** `client.chat(` or `client.v2.chat(`

## AWS Bedrock (`boto3`)

```python
import boto3

client = boto3.client("bedrock-runtime")
response = client.converse(modelId="anthropic.claude-3-sonnet", messages=[...])
response = client.invoke_model(modelId="...", body=json.dumps({...}))
```

**Pattern to match:** `*.converse(` or `*.invoke_model(`

## LiteLLM (`litellm`)

```python
import litellm

response = litellm.completion(model="gpt-4o", messages=[...])
response = await litellm.acompletion(model="gpt-4o", messages=[...])
```

**Pattern to match:** `litellm.completion(` or `litellm.acompletion(`

## Together AI (`together`)

```python
from together import Together

client = Together()
response = client.chat.completions.create(model="meta-llama/...", messages=[...])
```

**Pattern to match:** same as OpenAI — `*.chat.completions.create(`

## Mistral AI (`mistralai`)

```python
from mistralai import Mistral

client = Mistral()
response = client.chat.complete(model="mistral-large", messages=[...])
response = await client.chat.complete_async(model="mistral-large", messages=[...])
```

**Pattern to match:** `*.chat.complete(` or `*.chat.complete_async(`

## Ollama (`ollama`)

```python
import ollama

response = ollama.chat(model="llama3", messages=[...])
response = ollama.generate(model="llama3", prompt="...")
```

**Pattern to match:** `ollama.chat(` or `ollama.generate(`

## Raw HTTP LLM calls (`httpx`, `requests`, `aiohttp`) — IMPORTANT

Some projects call model APIs over **raw HTTP** instead of a vendor SDK (e.g. to use a feature the SDK lags on, like Gemini 3.x `thought_signature`). `neatlogs.wrap()` and ALL auto-instrumentation are **BLIND** to these — there is no SDK method to patch. They MUST be instrumented with a **manual span** where you set the I/O and token attributes by hand.

**Pattern to match — an HTTP POST whose URL is a known model endpoint:**

```python
# httpx (sync/async, stream or not) — the URL is the giveaway:
client.stream("POST", url, json=payload, ...)   # url contains :streamGenerateContent
await client.post(url, json=payload, ...)
# requests / aiohttp equivalents
requests.post(url, json=payload)
session.post(url, json=payload)
```

Endpoint hosts that mean "this is an LLM call":
- `generativelanguage.googleapis.com` / `aiplatform.googleapis.com` → `:generateContent` / `:streamGenerateContent` (Gemini)
- `api.openai.com/v1/chat/completions` / `/v1/responses`
- `api.anthropic.com/v1/messages`
- `api.groq.com`, `api.mistral.ai`, `api.together.xyz`, Azure OpenAI `*.openai.azure.com`, Bedrock runtime URLs

**How to instrument (manual span — set attributes yourself):**

```python
import json, neatlogs

# non-streaming
with neatlogs.trace("Gemini generate", kind="LLM") as span:
    span.set_attribute("neatlogs.llm.model_name", model)
    span.set_attribute("neatlogs.llm.provider", "google")
    # input: serialize the request messages you're about to POST
    span.set_attribute("neatlogs.llm.input", json.dumps({"messages": input_messages}))
    resp = await client.post(url, json=payload, headers=headers)
    data = resp.json()
    # output + tokens: pull from the HTTP response body
    span.set_attribute("neatlogs.llm.output", json.dumps({"role": "assistant", "content": output_text}))
    usage = data.get("usageMetadata", {})
    span.set_attribute("neatlogs.llm.token_count.prompt", usage.get("promptTokenCount", 0))
    span.set_attribute("neatlogs.llm.token_count.completion", usage.get("candidatesTokenCount", 0))
    span.set_attribute("neatlogs.llm.token_count.total", usage.get("totalTokenCount", 0))
```

For **streaming** over raw HTTP the span lifecycle is more involved (manual `__enter__`/`__exit__`, accumulate across chunks, close before the final yield for correct nesting, double-close guard) — follow **`references/raw-http-streaming-span.md`** exactly.

For the **exact request/response field paths per provider** (OpenAI Chat + Responses, Anthropic, Gemini Vertex + AI Studio; streaming + non-streaming; the token-location gotchas), see **`references/raw-http-llm-formats.md`**. First read the app's existing response-parsing code and tap the SAME variables; use the reference when the code parses loosely.

Use the canonical `neatlogs.*` attribute names (`neatlogs.llm.input` / `neatlogs.llm.output` / `neatlogs.llm.token_count.{prompt,completion,total}`) so the backend renders I/O and computes cost — do NOT invent keys.

### Authoritative attribute names — check the SDK before hand-setting any attribute

When you set span attributes BY HAND (manual spans / raw-HTTP), the exact `neatlogs.*` key names are not optional — the backend only renders keys it recognizes. The authoritative list ships INSIDE the installed SDK. Read it before writing attribute keys:

```bash
python -c "import neatlogs, pathlib; print(pathlib.Path(neatlogs.__file__).parent / 'config' / 'attribute-mapping.json')"
```

Open that JSON and use the canonical `neatlogs.*` output names exactly (e.g. `neatlogs.llm.input_messages.{i}.role` / `.content`, `neatlogs.llm.output_messages.{i}.role` / `.content`, `neatlogs.llm.input`, `neatlogs.llm.output`, `neatlogs.llm.model_name`, `neatlogs.llm.token_count.{prompt,completion,total,cache_read,reasoning}`, `neatlogs.span.kind`, and the `neatlogs.{tool,agent,retriever,embedding}.*` families). Never guess a key — if it isn't in that file, it won't render.

---

## Find ALL call-site variants (generalize one element at a time)

The patterns above are a starting set, not the full set. Real projects rename clients, re-export models, wrap SDKs in helpers, and mix in raw HTTP — so a single grep for `client.chat.completions.create` will miss sites. Use this loop to find every true call site (works for LLM, tool, retriever, and embedding sites alike):

1. **Anchor on one confirmed call.** Find one call you are certain about and read it. Note its three parts: the **method** (`.chat.completions.create`), the **receiver** (`client`), and the **import/source** (`from openai import OpenAI`).
2. **Generalize ONE element, re-grep, classify.** Hold the other two fixed and vary just one:
   - **Receiver:** the variable may be named anything (`llm`, `oai`, `self._client`, `get_client()`). Grep the method alone (`.chat.completions.create(`) to catch every receiver.
   - **Method:** the same receiver may expose sibling calls (`.responses.create`, `.chat.completions.create`, async `await ...`, `.stream`). Grep the receiver/import to surface its other methods.
   - **Import:** the same SDK may be imported under aliases or behind a wrapper module. Grep the package name (`openai`, `anthropic`) to find re-exports and helper modules that hide a call one level down.
3. **Classify each new match** against the patterns above (or as a tool/retriever/embedding site). Confirm by reading the body — a name is not proof.
4. **Repeat** with the next element until a pass turns up no new true matches.
5. **Sweep for raw HTTP last.** Grep for the model endpoint hosts (see the raw-HTTP section above) to catch sites that use no SDK at all — `wrap()` and auto-instrumentation are blind to these.

Each true match found this way still needs its `trace("<name>", kind=...)` / span exactly as the rest of this skill describes. Stop only when generalizing every element yields nothing new.

## How to Use This Reference

When scanning a file for LLM calls:
1. Look for any of the patterns above
2. Each match needs `with neatlogs.trace("<name>", kind="LLM", system_prompt_template=..., user_prompt_template=...)` wrapping it (`name` is the required first positional arg)
3. Extract the messages/prompt into `SystemPromptTemplate` + `UserPromptTemplate`
4. This applies even inside LangChain nodes — the handler captures the call metadata but NOT the prompt template structure for prompt management
