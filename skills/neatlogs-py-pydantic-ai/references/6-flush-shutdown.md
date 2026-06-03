# Step 6: Add flush() and shutdown()

## Scripts / CLI
```python
if __name__ == "__main__":
    try:
        main()
    finally:
        neatlogs.flush()
        neatlogs.shutdown()
```

## Servers (FastAPI/Flask)
init() once at startup; flush/shutdown on graceful shutdown (lifespan shutdown / SIGTERM), never per-request.

Do not omit flush — a script that exits without it loses the last batch of spans.
