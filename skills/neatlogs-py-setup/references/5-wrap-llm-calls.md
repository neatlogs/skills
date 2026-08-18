# Step 5: Verify One Capture Owner Per LLM Call

Classify every model call by its existing capture owner:

- `neatlogs.wrap(...)` for supported provider/framework instances
- `neatlogs.langchain_handler()` for LangChain/LangGraph
- `neatlogs.openai_agents_processor()` for OpenAI Agents
- framework hooks/processors/native telemetry for Strands and other supported frameworks
- provider instrumentor only when that provider has no wrapper
- no owner for unsupported SDKs and raw HTTP

If an owner exists, use it exactly once. Do not add `neatlogs.trace(kind="LLM")`, an LLM decorator, or a second provider/framework integration around the call. Do not rewrite user messages merely to instrument them.

Use a manual LLM trace only for the final category: a real LLM operation with no supported capture owner. The manual span must record complete input/output, model, usage, status, streaming completion, and errors using canonical attributes.

Custom WORKFLOW/CHAIN/AGENT spans are allowed around genuine multi-step orchestration. They must not duplicate a framework-owned chain/node/agent span or exist only to wrap one captured LLM call.

## Verify

- [ ] Each automatic operation has exactly one wrapper/handler/hook/processor/instrumentor.
- [ ] No manual LLM span/decorator surrounds an automatically captured call.
- [ ] Manual LLM spans exist only for unsupported/raw calls and carry complete semantics.
- [ ] A runtime trace has one canonical LLM span per real model call.
