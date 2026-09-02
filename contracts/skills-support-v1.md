# Public Skill support contract v1

[`skills-support-v1.json`](./skills-support-v1.json) is the public, machine-readable authority for Skill, SDK, Wizard, telemetry-schema, and backend-diagnostic compatibility.

Every published Skill archive contains an exact copy at `.neatlogs/skills-support-v1.json`. The release menu pins every archive and the support contract by SHA-256 and byte length. Download URLs are restricted to the versioned `neatlogs/skills` GitHub release; `latest` is used only to discover the menu, never as the final archive URL.

The contract intentionally distinguishes availability from a future interface. At this release, the required `neatlogs.doctor/v2` SDK command and `neatlogs.backend-diagnostic/v1` receipt are not released. Skills must therefore return `DOCTOR_UNAVAILABLE`, give the detected version and public upgrade guidance, and disable Doctor-gated automatic source edits. The Wizard's bundled Doctor v1 fixture is not an SDK Doctor and must not be presented as one.

Only entries in `safe_fix_allowlist` may become source or package changes after a compatible Doctor reports the same reason code as fixable. Every change still requires user approval. Credentials, private PII selectors, ingestion mappings, deduplication rules, root-selection rules, and finalizer implementation never belong in this contract.

Success requires the complete `success_requires` list. Installation, compilation, local span creation, HTTP acceptance, Kafka publication, raw persistence, or an uncorrelated trace is not enough.
