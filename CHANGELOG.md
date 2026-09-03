# Changelog

All notable changes to the Neatlogs skill packages are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.3.0] - 2026-09-03

### Added

- Added the public `neatlogs.skills-support/v1` compatibility contract covering Skill, SDK, Wizard, telemetry-schema, integration, reason-code, and backend-diagnostic compatibility.
- Added deterministic Skill archives with embedded public contracts, versioned canonical download URLs, SHA-256 digests, byte lengths, and a release checksum manifest.
- Added a versioned compatibility gate to every public Skill: read-only detection before edits, fail-closed Doctor capability checks, public reason-code remediation, explicit approval, rollback, and idempotency requirements.
- Added source-pinned package/import/mechanism metadata for every integration, including the current Python Azure OpenAI, Vertex, OpenRouter, and Claude Agent SDK wrappers.
- Added clean Python, Node.js, and Go execution smokes plus an immutable, release-ordered publication gate.

### Fixed

- Removed the retired TypeScript `traceContent` and `NEATLOGS_TRACE_CONTENT` guidance.
- Aligned TypeScript instrumentation guidance with the removed public registry: explicit wrappers, handlers, hooks, processors, and plugins are the only supported integration paths.
- Replaced the misleading bundled-Wizard Doctor gate with truthful `DOCTOR_UNAVAILABLE` behavior until SDK Doctor v2 and correlated backend receipts are released.
- Made automated edits fail closed, require a public allowlisted reason code plus user approval, and require rollback/idempotency checks.
- Kept TypeScript Strands explicitly unsupported because its exported helper rejects at runtime.

## [1.2.4] - 2026-08-19

### Added

- Documented `@neatlogs/codex` for tracing Codex coding sessions and distinguished it from the Agent Skills that teach coding agents to instrument user applications.

### Fixed

- Corrected TypeScript retriever documentation to use canonical `neatlogs.retriever.documents.N.{content,id,score,metadata}` attributes for every returned document without client-side truncation.
- Corrected direct-ingest guidance so standard `gen_ai.retrieval.documents` maps to the canonical aggregate `neatlogs.retriever.documents` attribute.
- Corrected Python evaluator guidance so ordinary custom evaluator and memory functions use supported `@span` kinds, while scoped evaluator traces are reserved for direct metadata or callbacks without a decorator boundary.
- Made live verification select the exact process-scoped marker trace, require the deployed hosted MCP contract, poll finalization, and inspect every paginated span without falling back to the latest project trace.

## [1.2.3] - 2026-08-19

### Added

- Added explicit completion gates across SDK and direct-ingest skills: build or typecheck changed code, restart the process that loads instrumentation, exercise a representative real path, and confirm the complete persisted trace in Neatlogs.
- Added coding-agent verification guidance that uses the hosted Neatlogs MCP tools, polls while processing is incomplete, paginates the entire span tree, and checks input/output on every non-LOG span.
- Added complete custom-instrumentation guidance for unsupported model providers, frameworks, vector databases, retrievers, rerankers, evaluators, guardrails, tools, embeddings, and custom orchestration.
- Added framework-specific composition rules for mixing wrappers, callbacks, hooks, processors, and instrumentors with custom workflow and operation spans.
- Added a generic retrieval-and-generation workflow example derived from the observed failure mode without retaining customer-specific names or environment details.

### Changed

- Made wrappers, callback handlers, hooks, processors, and framework instrumentors the sole owners of supported LLM calls; manual LLM spans are now reserved for raw or unsupported calls.
- Removed prompt-template rewrites and prompt-template-specific instrumentation from the Python and TypeScript guidance.
- Clarified when to use decorators versus scoped traces, including async, streaming, workflow, chain, tool, retrieval, embedding, reranking, evaluation, and guardrail boundaries.
- Updated Python LangChain/LangGraph guidance for synchronous and asynchronous graph invocations and handler placement at the graph boundary.
- Updated Go guidance for `WrapGenAI`, custom span helpers, initialization, identity, verification, and mixed supported/unsupported instrumentation.
- Standardized managed ingestion and MCP configuration on `https://ingest.neatlogs.com`; users do not pass an endpoint to SDK initialization.
- Replaced customer-specific recall terminology with a reusable retrieval-and-generation workflow.

### Fixed

- Fixed instructions that could create duplicate LLM spans by combining a supported wrapper/handler/hook/processor with a manual LLM decorator or trace.
- Fixed vague `trace()` guidance that implied scoped traces were only for grouping operations instead of representing specific custom span kinds and recording their canonical attributes.
- Fixed completion instructions that could let an agent stop after source edits or offline checks without rebuilding, restarting, exercising the actual path, and confirming live ingestion.
- Fixed guidance that could expose secrets or copy user environment details into skills, logs, examples, or generated instrumentation.
- Fixed legacy `neatlogs.retrieval.*` naming in favor of the canonical `neatlogs.retriever.*` namespace.

[Unreleased]: https://github.com/neatlogs/skills/compare/skills-v1.3.0...HEAD
[1.3.0]: https://github.com/neatlogs/skills/compare/skills-v1.2.4...skills-v1.3.0
[1.2.4]: https://github.com/neatlogs/skills/compare/skills-v1.2.3...skills-v1.2.4
[1.2.3]: https://github.com/neatlogs/skills/compare/skills-v1.2.2...skills-v1.2.3
