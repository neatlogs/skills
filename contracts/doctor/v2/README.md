# NeatLogs SDK Doctor v2 contract

[`neatlogs-doctor.schema.json`](neatlogs-doctor.schema.json) is the public,
language-neutral result contract emitted by the installed Python, TypeScript,
and Go SDK Doctor commands.

Contract: `neatlogs.doctor/v2`

Schema SHA-256: `e415d448f73eb6e8a2967b0379aa4d995d9087f83d0ad2e1a1c8e7295ee37c26`

Local mode is network-free and validates a controlled in-process capture. Probe
mode sends the same four-span fixture through the normal `/v1/traces` path and
reads that exact trace through `/api/traces/v3/{trace_id}`. A passing probe must
contain exactly one WORKFLOW root, one AGENT child with one LLM child, and one
TOOL child of the root, with no duplicates. Numeric token values must remain
numbers; the deterministic fixture uses 11 prompt, 7 completion, and 18 total
tokens.

Reason and remediation codes are intentionally pattern-constrained rather than
enumerated so newer SDKs can add codes without breaking older consumers.
Consumers must preserve unknown codes and must not infer an automatic fix.
`checks[].details` is a sanitized diagnostic projection and accepts primitive
values only; credentials, request or response bodies, span payloads, and
internal service topology are not part of this public contract.

The fixtures are conformance snapshots, not a supported-version allowlist.
`local-pass.json` comes from the published TypeScript SDK Doctor with volatile
IDs, digests, and durations normalized. Validation pins its emitted success
checks so schema-only validation cannot hide reason-code drift. Consumers must
use the latest published stable SDK, accept newer compatible releases that emit
this Doctor capability, and never downgrade a compatible installation.
