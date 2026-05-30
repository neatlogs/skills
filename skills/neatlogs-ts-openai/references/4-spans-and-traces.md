# Step 4: Wrap Orchestration (span) + LLM Calls (trace + templates)

## span() — bind a WORKFLOW root

Wrap the user-facing entry function (the one that runs a unit of work) with `span({ kind: 'WORKFLOW' }, fn)`. `span()` returns a wrapped function; call it as normal.

```typescript
import { span } from "neatlogs";

const run = span({ kind: "WORKFLOW", name: "answer" }, async (query: string) => {
  // ... orchestration that makes LLM calls ...
});
await run(userQuery);
```

Use `kind: "AGENT"` for an autonomous agent loop, `"CHAIN"` for internal multi-step orchestration.

## trace() + templates — around each LLM call

Wrap each LLM call with `trace({ kind:'LLM', promptTemplate, userPromptTemplate }, fn)`. COMPILE the templates and pass the compiled output to the actual SDK call. `compile()` returns a string for a string template, ready for `system:`/message `content`.

### OpenAI

```typescript
import { PromptTemplate, UserPromptTemplate, trace } from "neatlogs";

const SYS_TPL  = new PromptTemplate("You are a helpful assistant specializing in {{domain}}.");
const USER_TPL = new UserPromptTemplate("{{query}}");

const answer = span({ kind: "WORKFLOW", name: "answer" }, async (query: string) =>
  trace({ name: "llm_call", kind: "LLM", promptTemplate: SYS_TPL, userPromptTemplate: USER_TPL }, async () => {
    const sys = SYS_TPL.compile({ domain: "science" }) as string;
    const user = USER_TPL.compile({ query }) as string;
    const res = await client.chat.completions.create({
      model: "gpt-4o",
      messages: [{ role: "system", content: sys }, { role: "user", content: user }],
    });
    return res.choices[0].message.content;
  }),
);
```

### Anthropic (system is a separate param)

```typescript
const res = await client.messages.create({
  model: "claude-sonnet-4-6",
  max_tokens: 1024,
  system: SYS_TPL.compile({ industry: "tech" }) as string,   // compiled system string
  messages: [{ role: "user", content: USER_TPL.compile({ query }) as string }],
});
```

## CRITICAL rules

- **Compile and use**: the template passed to `trace()` MUST be `.compile()`d and that output sent to the LLM. A template declared in `trace()` but not used in the call is decorative/broken.
- **`{{variables}}` = dynamic data only** (user input, retrieved context, runtime values). NEVER make a whole authored prompt a `{{variable}}`. If a system prompt is SELECTED from a fixed set at runtime, make one `PromptTemplate` per variant (real text baked in) and pick by key — not a single `{{system_prompt}}` passthrough.
- Static/constant prompts still become templates (with the real text), so they're versionable in the dashboard.
- Define templates at module scope; `UPPERCASE_TPL` naming.

## WRONG vs RIGHT

```typescript
// ❌ WRONG — template declared but call uses a raw string. Template is decorative.
const SYS = new PromptTemplate("You are helpful.");
await trace({ kind: "LLM", promptTemplate: SYS }, async () =>
  client.chat.completions.create({ messages: [{ role:"system", content:"You are helpful." }, ...] }));

// ✅ RIGHT — compile the template, send the compiled value.
await trace({ kind: "LLM", promptTemplate: SYS, userPromptTemplate: USER }, async () => {
  const sys = SYS.compile() as string;
  return client.chat.completions.create({ messages: [{ role:"system", content: sys }, ...] });
});
```

## Verify
- [ ] User-facing entry wrapped with `span({ kind: "WORKFLOW" }, ...)`.
- [ ] Each LLM call wrapped with `trace({ kind:"LLM", promptTemplate, userPromptTemplate }, ...)`.
- [ ] Templates are `.compile()`d and the result is what's actually sent.
- [ ] No whole-prompt-as-variable; runtime-selected prompts use one template per variant.
