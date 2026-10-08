# Trace readback through the supported Public API

Source: `neatlogs/neatlogs-app` `staging` commit
`7253b22987c749cb4b1b50c063f6903c313273d3`, especially
[`observability-contracts.ts`](https://github.com/neatlogs/neatlogs-app/blob/7253b22987c749cb4b1b50c063f6903c313273d3/backend/src/lib/public-api/observability-contracts.ts),
[`observability operations`](https://github.com/neatlogs/neatlogs-app/blob/7253b22987c749cb4b1b50c063f6903c313273d3/backend/src/lib/public-api/operation-definitions/observability.ts), and
[`CLI observability commands`](https://github.com/neatlogs/neatlogs-app/blob/7253b22987c749cb4b1b50c063f6903c313273d3/cli/src/commands/observability.ts).

## Commands and response shapes

| Need | CLI | Public API |
| --- | --- | --- |
| Exact trace metadata | `neatlogs traces get <trace-id> --json` | `GET /api/v1/public/traces/{traceId}` |
| Safe span metadata page | `neatlogs traces spans list <trace-id> --limit 50 --json` | `GET /api/v1/public/traces/{traceId}/spans?limit=50` |
| One safe span | `neatlogs traces spans get <trace-id> <span-id> --json` | `GET /api/v1/public/traces/{traceId}/spans/{spanId}` |
| Bounded safe export | `neatlogs traces export <trace-id> --format json` | `GET /api/v1/public/traces/{traceId}/export?format=json` |

The trace detail's `data` object contains `traceId`, `sessionId`,
`traceName`, `workflowName`, `status`, `finalizationStatus`, `spansCount`,
`llmCallsCount`, `toolCallsCount`, `totalTokens`, and other safe summary fields.
It does not contain a `spans` array. The span list's `data` object contains
`spans` and `page` (`limit`, `hasMore`, `nextCursor`). Each safe span has
`spanId`, `parentSpanId`, `spanName`, `spanType`, `status`, `promptTokens`,
`completionTokens`, and `totalTokens`. These names differ from the dashboard
route's `_id`, `spanCount`, `totalTokensUsed`, `span_id`, `parent_span_id`,
`node_name`, and `node_type` fields.

The page limit is 1-50. Fetch subsequent pages with `--cursor <nextCursor>`
until the cursor is null or a task-specific safety ceiling is reached. If a
ceiling is reached, label the result partial and do not claim all parents or
spans were checked. A trace summary count can be compared with the collected
spans only after complete pagination and when the same projection is used.

The public span list reads the finalized [`spans_simplified` projection](https://github.com/neatlogs/neatlogs-app/blob/7253b22987c749cb4b1b50c063f6903c313273d3/backend/src/services/PublicObservabilityRead/span-repository.ts#L158).
The finalizer can [repair parent links and normalize roots](https://github.com/neatlogs/neatlogs-app/blob/7253b22987c749cb4b1b50c063f6903c313273d3/backend/src/workers/trace-finalizer/simplified-view.ts#L5759),
including [attaching extra parentless spans beneath one canonical root](https://github.com/neatlogs/neatlogs-app/blob/7253b22987c749cb4b1b50c063f6903c313273d3/backend/src/workers/trace-finalizer/span-tree.ts#L195).
Therefore, complete pagination covers all available *public projected* spans;
one public root or a valid public parent tree does not prove the emitted span
topology had one root or those same parent links. If original emitted topology
matters, inspect raw spans only with separate authorization or mark that aspect
unverified. A normal metadata read need not be widened to payload access.

## Interpret the result

1. Match the exact trace ID and selected project to the workflow being tested.
2. Treat `finalizationStatus: "pending"` (or a span read that reports its
   projection is not ready) as incomplete; retry for a bounded period.
   `finalizationStatus: "dlq"` is a failure requiring investigation, not
   another flush. A null finalization status is unknown.
3. Once finalized, inspect the expected semantic spans and parent IDs in the
   canonical public projection. The public response is deliberately safe
   metadata; it omits arbitrary span
   attributes, raw input/output, and internal storage details. Use a
   separately authorized payload read only when the user's task needs it.
4. `totalTokens: 0` does not by itself prove an SDK regression. Token usage
   can be absent from a provider response. Check the operation and provider
   semantics before treating zero as an error.
5. Do not call a trace healthy merely because the HTTP request succeeded or
   a few bounded checks passed. Report exactly what was observed and what
   remains unverified.

The SDK Doctor probe is a separate controlled test of installed SDK capture
and transport. Its internal read route and marker header are not the general
purpose customer trace-read API.
