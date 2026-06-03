# Step 6: flush() and shutdown()

```python
if __name__ == "__main__":
    try:
        main()
    finally:
        neatlogs.flush()
        neatlogs.shutdown()
```
Servers: init once at startup; flush/shutdown on graceful shutdown only.
