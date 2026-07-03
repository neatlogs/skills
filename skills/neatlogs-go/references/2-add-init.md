# Step 2: Add neatlogs.Init()

## Action

1. Find the application entry point (`main.go`, or wherever the process starts).
2. `Init` MUST run **once**, early, before any LLM/ADK work. It registers the global OTel TracerProvider — call it a single time per process.
3. Call `Init` and `defer shutdown(ctx)` immediately. `shutdown` flushes buffered spans; without it, spans exit with the process **unexported and lost**.

## Pattern

```go
package main

import (
    "context"
    "log"
    "os"

    "github.com/neatlogs/neatlogs-go"
)

func main() {
    ctx := context.Background()

    shutdown, err := neatlogs.Init(ctx, neatlogs.Config{
        APIKey:       os.Getenv("NEATLOGS_API_KEY"),
        WorkflowName: "my-service",
        Tags:         []string{"prod"},
        Debug:        true,
    })
    if err != nil {
        log.Fatal(err)
    }
    defer shutdown(ctx) // flushes spans — REQUIRED

    // ... app work ...
}
```

`Init` returns `(ShutdownFunc, error)`.

## Config fields

`neatlogs.Config` has **only** these fields:

| Field           | Type       | Notes                                                          |
| --------------- | ---------- | -------------------------------------------------------------- |
| `APIKey`        | `string`   | Required for export. Falls back to `NEATLOGS_API_KEY` env.     |
| `Endpoint`      | `string`   | Base URL, no `/v1/traces`. Empty → managed cloud. Env fallback: `NEATLOGS_ENDPOINT`. |
| `WorkflowName`  | `string`   | Logical name for this service/workflow.                        |
| `Tags`          | `[]string` | Free-form tags stamped on traces.                              |
| `Debug`         | `bool`     | Verbose SDK logging.                                           |
| `DisableExport` | `bool`     | Build spans but skip export (local/testing).                   |

There is **NO session or end-user field** on `Config` — identity is per-request, not process-global (see `sessions-and-end-users.md`).

## WRONG vs RIGHT

```go
// ❌ WRONG — no defer shutdown. Process exits, buffered spans never export → nothing in dashboard.
shutdown, _ := neatlogs.Init(ctx, neatlogs.Config{APIKey: os.Getenv("NEATLOGS_API_KEY"), WorkflowName: "my-service"})
_ = shutdown
```

```go
// ✅ RIGHT — defer shutdown(ctx) guarantees a final flush.
shutdown, err := neatlogs.Init(ctx, neatlogs.Config{APIKey: os.Getenv("NEATLOGS_API_KEY"), WorkflowName: "my-service"})
if err != nil {
    log.Fatal(err)
}
defer shutdown(ctx)
```

## Verify BEFORE moving on

1. `Init` is called exactly once, near process start.
2. `defer shutdown(ctx)` sits right after the error check.
3. No invented Config fields — only the six above exist.
