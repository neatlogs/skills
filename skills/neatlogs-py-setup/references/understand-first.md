# Understand the Agentic System First

Do this BEFORE editing anything. You cannot instrument what you do not understand — guessing produces wrong span kinds, missed call sites, and traces that misrepresent the app. Build a small, evidence-backed picture of the system first, then let that picture drive every later step.

This is a read-only investigation phase. No installs, no `init()`, no decorators yet.

## Phase 1 — Orientation

Goal: know where the program starts and which LLM/agent machinery it leans on.

1. **Find the entry points.** Where does execution actually begin?
   - Web routes / handlers (FastAPI, Flask, Django views, ASGI apps).
   - A `main()` / `if __name__ == "__main__":` block, a CLI command (Click/Typer/argparse), a worker/consumer loop, a scheduled job, a notebook cell.
   - There may be more than one. List each as `path:line`.
2. **Find the AI libraries in play.** Read `pyproject.toml` / `requirements*.txt` / lockfiles, then grep imports in the source. Note every LLM SDK (openai, anthropic, google-genai, groq, …) and every agent framework (crewai, langchain/langgraph, dspy, agno, google-adk, strands, pydantic-ai, openai-agents). Raw-HTTP clients (httpx/requests/aiohttp) matter too — they can hide LLM calls.
3. **Confirm what's actually used, not just installed.** A dependency in the manifest that is never imported does not need instrumentation.

Record findings as a flat list of `path:line` references. If you cannot see an entry point or an import, say "need to inspect X" — do not invent one.

## Phase 2 — Map roles and connections

For each candidate you found, answer two questions with evidence.

**(a) What agentic role does it play?** Classify into one of the span kinds the rest of this skill uses (see `references/span-kinds.md`):

| Role | What it looks like in code |
|---|---|
| LLM call | a model request: `*.chat.completions.create`, `*.messages.create`, `llm.invoke`, `generate_content`, a POST to a model endpoint |
| tool | a discrete capability the agent can call — `@tool`, a function passed to an agent's `tools=`, an MCP handler |
| retriever | query in, documents out — vector store `.search` / `.similarity_search`, a RAG fetch |
| reranker | takes candidate docs + query, reorders them |
| embedding | text → vector — `.embeddings.create`, `embed_documents` |
| chain | a fixed sequence: pre-process → LLM → post-process |
| agent | autonomous decision-maker with a role/goal that picks tools and makes LLM calls in a loop |
| workflow | the top-level orchestration that runs the whole thing once per request/run |

**(b) How are the pieces wired together?** Trace the data flow, not just the file list:
- Which agent owns which tools? (look at the `tools=` list / registration)
- What feeds each LLM call — a prompt template, retrieved docs, tool results, raw user input?
- Which function is the outermost orchestrator that everything nests under?
- Where does control loop (agent → tool → agent again)?

## Anti-hallucination rules

- **Cite `file:line` for every finding.** "It's an LLM call" is worthless without "because line 42 calls `client.chat.completions.create`."
- **A name is not evidence.** `retrieve()` might call an LLM; `process_agent()` might be a plain dict transform. Confirm by reading the body before classifying.
- **State uncertainty explicitly.** Write "need to inspect `tools/search.py` to confirm whether it hits a vector store" instead of guessing the role.
- **Used, not just installed** — and **reached, not just defined.** A function nobody calls on the live path is not in the inventory.

## Which entry points are WORKFLOWS (and which are NOT)

A WORKFLOW span is the trace ROOT of a meaningful unit of work — a feature that actually does AI/agent activity. NOT every route/handler is a workflow:

- ✅ WORKFLOW: an entry point that (directly or transitively) reaches an LLM / agent / tool / retriever / embedding — i.e. it produces a trace worth looking at (a chat endpoint, a generate/analyze/summarize route, an agent run, a queue handler that calls a model).
- ❌ NOT a workflow (instrument with NOTHING, or only a child span if it does real work): pure CRUD / read endpoints that just hit a database or cache and return — `list_*`, `get_*`, `create_*`, `update_*`, `delete_*`, health/readiness/ping. Rooting these produces empty, content-free traces on every call — noise that buries the real agent traces. When in doubt, ask: "if this ran, would the trace contain an LLM/tool/retriever span?" If no → it is not a workflow, skip it.

Trace each entry point's call graph: does any path from it reach a model/agent/tool? Only then is it a WORKFLOW.

## FIRST TRACE FAST — instrument one complete path first, then the rest

Your FIRST goal is to get ONE proper trace to the platform as quickly as possible (like PostHog lands a first event in minutes), THEN broaden to full coverage. A "proper" first trace = a WORKFLOW root with at least its LLM call nested under it (NOT an orphan LLM span — those get dropped). So:

1. From the inventory, pick the SIMPLEST high-value feature — ideally a NON-streaming request→LLM→response path (e.g. a `generate_*` / `analyze_*` route), the one with the fewest moving parts.
2. Instrument THAT path end-to-end FIRST: init() + the feature's WORKFLOW root + its LLM call (+ wrap the client). Make it compile.
3. Tell the user how to exercise it (the curl / command) so a trace lands and confirms the pipeline works.
4. THEN continue instrumenting the remaining workflows/tools/retrievers for full coverage.

Do not leave init()/first-feature until the very end — front-load one working path so time-to-first-trace is minutes, not the whole run.

## Output — the component inventory

Produce a short table that drives the rest of the setup. One row per component. Mark which row is your **FIRST-TRACE path** (instrument it first):

| Component (`file:line`) | Role / kind | Wiring (uses / feeds) | How to instrument |
|---|---|---|---|
| `app/run.py:18 chat()` | WORKFLOW | calls `agent.run`; entry point | `@neatlogs.span(kind="WORKFLOW")` (step 4) |
| `agents/research.py:30` | AGENT | owns `web_search`, `summarize` tools | per framework skill / step 4 |
| `clients/llm.py:55` | LLM call | fed by prompt template + retrieved docs | `with neatlogs.trace("llm_call", kind="LLM")` (step 5) |
| `tools/search.py:12` | TOOL → RETRIEVER | queries Pinecone, returns docs | `@neatlogs.span(kind="RETRIEVER")` (step 6) |

The "How to instrument" column points at the concrete step/reference: WORKFLOW/AGENT/CHAIN/TOOL/RETRIEVER decorators (`references/4-decorate-functions.md`, `6-decorate-tools.md`, `span-kinds.md`), LLM calls (`references/5-wrap-llm-calls.md`, `llm-call-patterns.md`), and raw-HTTP LLM sites (`references/raw-http-llm-formats.md`). What a framework wrapper/handler already covers is in `references/auto-instrumented.md` — don't double-instrument those.

Once the inventory is complete and evidence-backed, proceed to the numbered steps and instrument each row.
