# Span kinds (Strands)

Captured natively (Strands' own OTel, classified by the mapper):
- **agent** — invoke_agent
- **llm** — model call
- **tool** — execute_tool

Your own code: `@neatlogs.span(kind="WORKFLOW"|"CHAIN"|...)`.
