# Step 6b: Instrument Retrievers, Memory, Guardrails, Sessions & Provenance

Capturing LLM and tool spans alone is not enough for accurate automated evaluation or step-by-step replay/backtracking. Make sure every RAG/retrieval lookup, memory operation, guardrail check, multi-turn session, and deployment version is explicitly captured.

## 1. Retrievers, Rerankers, Memory & Guardrails

If a framework wrapper or vector-DB instrumentation does NOT already capture your retrieval or memory calls (for example, custom SQL/BM25 search, hybrid pipelines, custom rerankers, or guardrails), decorate them directly:

```python
import neatlogs

@neatlogs.span(kind="RETRIEVER", name="search_knowledge_base", replay=True)
def search_knowledge_base(query: str) -> list[dict]:
    rows = db.search(query, limit=5)
    return [
        {
            "id": row.id,
            "content": row.body,
            "score": row.similarity,
            "updated_at": row.updated_at.isoformat(),  # freshness timestamp
        }
        for row in rows
    ]

@neatlogs.span(kind="RERANKER", name="rerank_docs", replay=True)
def rerank_docs(query: str, docs: list[dict]) -> list[dict]:
    ...

@neatlogs.span(kind="GUARDRAIL", name="check_policy", replay=True)
def check_policy(reply: str) -> dict:
    ...
```

Rules for retrieval & step spans:
- Return structured document dicts with `id`, `content`, `score`, and a freshness timestamp (`updated_at` / `created_at` / `timestamp`) whenever available so evaluators can distinguish stale knowledge from model hallucination.
- Pass `replay=True` on deterministic JSON-serializable `RETRIEVER`, `RERANKER`, `VECTOR_STORE`, `MEMORY`, and `GUARDRAIL` functions so traces can be backtracked and forked from any step without re-hitting live databases.
- Never double-instrument retrievers already covered by a framework handler or vector-DB integration (see [`auto-instrumented.md`](auto-instrumented.md)).

## 2. Multi-Turn Sessions & End-Users (Required for Chat / Agent Apps)

If the app serves multi-turn conversations or per-customer workflows, bind `session_id` and `end_user_id` on the trace root (or via `neatlogs.identify(...)` for wrapper-only code). See [`sessions-and-end-users.md`](sessions-and-end-users.md) for all three patterns.

- **NEVER** pass `trace_id` or a fresh `uuid4()` per turn as `session_id` — that breaks multi-turn conversation grouping.
- Reuse the application's real conversation, thread, ticket, or chat ID across every turn.

## 3. Environment, Release & Prompt Provenance

Pass explicit `environment` and `release` in `neatlogs.init()` (or set `NEATLOGS_ENVIRONMENT` and `NEATLOGS_RELEASE` in deployment config), and stamp `prompt_version` on the `WORKFLOW` root when prompts are versioned:

```python
neatlogs.init(
    api_key=os.getenv("NEATLOGS_API_KEY"),
    workflow_name="support-agent",
    environment=os.getenv("NEATLOGS_ENVIRONMENT", "production"),
    release=os.getenv("NEATLOGS_RELEASE"),
)

@neatlogs.span(kind="WORKFLOW", name="answer_ticket", prompt_version="support-v3")
def answer_ticket(user_message: str, session_id: str) -> str:
    ...
```

## 4. Checkpoints & Diagnostics for Multi-Step Loops (Optional)

For long-running or branching agent loops where you want deterministic time-travel checkpoints or structured non-fatal diagnostics, call the fail-open helpers on the active span:

```python
neatlogs.checkpoint(
    "after_retrieval",
    state={"ticket_id": ticket_id, "doc_count": len(docs)},
    state_delta={"escalated": False},
)

if stale_docs:
    neatlogs.report_diagnostic(
        "stale_data",
        "Retrieved policy document is older than 90 days",
        severity="warn",
        details={"doc_id": stale_docs[0]["id"]},
    )
```

Both helpers are bounded, fail-open, and scrub secrets automatically — never add blocking network I/O or per-request `neatlogs.flush()` calls on server hot paths.
