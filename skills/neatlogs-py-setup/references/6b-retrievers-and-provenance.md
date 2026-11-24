# Step 6b: Instrument Retrievers, Memory, Guardrails, Sessions & Provenance

> **Version prerequisite (`neatlogs >= 1.5.0` / PR #290):** Check the installed SDK version first (`python -c "import neatlogs; print(neatlogs.__version__)"`).
> - **Works on all versions (including `v1.4.x`):** `@neatlogs.span(kind="RETRIEVER" | "MEMORY" | "GUARDRAIL")` (without `replay=True`), `neatlogs.trace(..., kind="RERANKER" | "VECTOR_STORE")`, `updated_at` on retrieved docs, and `session_id` / `end_user_id` on trace roots.
> - **Requires `neatlogs >= 1.5.0`:** `replay=True` on non-`TOOL` span kinds (`RETRIEVER`, `RERANKER`, `VECTOR_STORE`, `MEMORY`, `GUARDRAIL`), `@neatlogs.span(kind="RERANKER" | "VECTOR_STORE")`, `environment` / `release` on `init()`, `prompt_version` / `checkpoint_id` on `@span()` / `trace()`, `neatlogs.checkpoint()`, and `neatlogs.report_diagnostic()`. Do **not** emit these on `v1.4.x` apps or they will fail with `ValueError`, `TypeError`, or `AttributeError` at import/startup.

Capturing LLM and tool spans alone is not enough for accurate automated evaluation or step-by-step replay/backtracking. Make sure every RAG/retrieval lookup, memory operation, guardrail check, multi-turn session, and deployment version is explicitly captured.

## 1. Retrievers, Rerankers, Memory & Guardrails

If a framework wrapper or vector-DB instrumentation does NOT already capture your retrieval or memory calls (for example, custom SQL/BM25 search, hybrid pipelines, custom rerankers, or guardrails), decorate them directly (on `v1.4.x`, omit `replay=True` on non-`TOOL` spans and use `with neatlogs.trace("rerank_docs", kind="RERANKER"):` instead of `@span(kind="RERANKER")`):

```python
import neatlogs

# On neatlogs >= 1.5.0 (omit replay=True on v1.4.x)
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

# Requires neatlogs >= 1.5.0 (on v1.4.x use neatlogs.trace("rerank_docs", kind="RERANKER"))
@neatlogs.span(kind="RERANKER", name="rerank_docs", replay=True)
def rerank_docs(query: str, docs: list[dict]) -> list[dict]:
    ...

# On neatlogs >= 1.5.0 (omit replay=True on v1.4.x)
@neatlogs.span(kind="GUARDRAIL", name="check_policy", replay=True)
def check_policy(reply: str) -> dict:
    ...
```

Rules for retrieval & step spans:
- Return structured document dicts with `id`, `content`, `score`, and a freshness timestamp (`updated_at` / `created_at` / `timestamp`) whenever available so evaluators can distinguish stale knowledge from model hallucination.
- On `neatlogs >= 1.5.0`, pass `replay=True` on deterministic JSON-serializable, non-generator `RETRIEVER`, `RERANKER`, `VECTOR_STORE`, `MEMORY`, and `GUARDRAIL` functions so traces can be backtracked and forked from any step without re-hitting live databases (omit `replay=True` on non-`TOOL` spans for `v1.4.x`).
- Never double-instrument retrievers already covered by a framework handler or vector-DB integration (see [`auto-instrumented.md`](auto-instrumented.md)).

## 2. Multi-Turn Sessions & End-Users (Required for Chat / Agent Apps)

If the app serves multi-turn conversations or per-customer workflows, bind `session_id` and `end_user_id` on the trace root (or via `neatlogs.identify(...)` for wrapper-only code). See [`sessions-and-end-users.md`](sessions-and-end-users.md) for all three patterns.

- **NEVER** pass `trace_id` or a fresh `uuid4()` per turn as `session_id` — that breaks multi-turn conversation grouping.
- Reuse the application's real conversation, thread, ticket, or chat ID across every turn.

## 3. Environment, Release & Prompt Provenance (`neatlogs >= 1.5.0`)

After verifying `neatlogs >= 1.5.0` is installed, pass explicit `environment` and `release` in `neatlogs.init()` (or set `NEATLOGS_ENVIRONMENT` and `NEATLOGS_RELEASE` in deployment config — do not hardcode `"production"` as a fallback for local runs), and stamp `prompt_version` on the `WORKFLOW` root when prompts are versioned:

```python
# Requires neatlogs >= 1.5.0 (omit environment/release/prompt_version on v1.4.x)
neatlogs.init(
    api_key=os.getenv("NEATLOGS_API_KEY"),
    workflow_name="support-agent",
    environment=os.getenv("NEATLOGS_ENVIRONMENT"),
    release=os.getenv("NEATLOGS_RELEASE"),
)

@neatlogs.span(kind="WORKFLOW", name="answer_ticket", prompt_version="support-v3")
def answer_ticket(user_message: str, session_id: str) -> str:
    ...
```

## 4. Checkpoints & Diagnostics for Multi-Step Loops (Optional, `neatlogs >= 1.5.0`)

On `neatlogs >= 1.5.0`, for long-running or branching agent loops where you want deterministic time-travel checkpoints or structured non-fatal diagnostics, call the fail-open helpers on the active span (`category` is the first parameter of `report_diagnostic`; valid `severity` values are `"info"`, `"warning"`, `"error"`, `"critical"`):

```python
# Requires neatlogs >= 1.5.0
# Preferred digest-only path when state may contain PII or secrets:
# pass `state` (hashed into `state_digest`) and omit `state_delta`.
neatlogs.checkpoint(
    "after_retrieval",
    state={"ticket_id": ticket_id, "doc_count": len(docs)},
)

# Only pass `state_delta` with allowlisted, already-sanitized, non-sensitive fields:
# neatlogs.checkpoint(
#     "after_policy_check",
#     state={"ticket_id": ticket_id, "step": "policy"},
#     state_delta={"escalated": False},
# )

if stale_docs:
    neatlogs.report_diagnostic(
        category="stale_data",
        message="Retrieved policy document is older than 90 days",
        severity="warning",
        details={"doc_id": stale_docs[0]["id"]},
    )
```

Privacy & safety rules for checkpoints and diagnostics:
- **No automatic secret or PII scrubbing:** `state_delta` (and diagnostic `details`) are serialized and exported as span attributes, and application masking is not guaranteed by default. Callers **MUST** pass only allowlisted, already-sanitized, non-sensitive fields in `state_delta` and `details`.
- **Prefer the digest-only path:** When loop state may contain PII, customer content, or secrets, hash sensitive state into `state_digest` by passing `state=...` and **omitting `state_delta`**.
- Both helpers are bounded and fail-open — never add blocking network I/O or per-request `neatlogs.flush()` calls on server hot paths.
