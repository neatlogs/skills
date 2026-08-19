# Changelog

All notable changes to the Neatlogs skill packages are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.2.4] - 2026-08-19

### Added

- Documented `@neatlogs/codex` for tracing Codex coding sessions and distinguished it from the Agent Skills that teach coding agents to instrument user applications.

### Fixed

- Corrected TypeScript retriever documentation to use canonical `neatlogs.retriever.documents.N.{content,id,score,metadata}` attributes for every returned document without client-side truncation.

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

[Unreleased]: https://github.com/neatlogs/skills/compare/skills-v1.2.4...HEAD
[1.2.4]: https://github.com/neatlogs/skills/compare/skills-v1.2.3...skills-v1.2.4
[1.2.3]: https://github.com/neatlogs/skills/compare/skills-v1.2.2...skills-v1.2.3
