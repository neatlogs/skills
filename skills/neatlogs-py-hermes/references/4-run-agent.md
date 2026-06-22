# Step 4: Run the agent (no per-call changes needed)

Because `init(instrumentations=["hermes", "openai"])` patched the `AIAgent` class,
you do NOT change how the agent is called — just construct and run it as usual.

```python
# (init + `from run_agent import AIAgent` already done in step 2)

agent = AIAgent(
    model="openai/gpt-4o-mini",          # OpenRouter slug
    api_key=os.getenv("OPENROUTER_API_KEY"),
    max_iterations=4,
)

result = agent.run_conversation("Explain distributed tracing in one paragraph.")
print(result)
```

Produces:
```
AGENT  hermes.run_conversation
  ↳ LLM   chat.completions.create   (via OpenRouter)
  ↳ TOOL  hermes.tool.<name>        (if the model calls a tool)
```

## Optional — wrap() form
`agent = neatlogs.wrap(AIAgent(...))` is equivalent (same class-level patch).
Prefer the `instrumentations=[...]` form from step 2; don't do both.

## Rules
- The AGENT span is a valid trace root — no WORKFLOW wrapper is required for a
  single agentic run.
- Do NOT wrap a single `agent.run_conversation()` call in its own `@span`/`trace`.
