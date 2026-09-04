---
name: neatlogs-validate
description: Use AFTER running any neatlogs-py-* or neatlogs-ts-* (or neatlogs-go) wizard, to confirm the SDK was installed, init()'d, and is actually exporting traces to the dashboard. Runs a 5-check checklist (SDK present in deps, init() called once at process start, NEATLOGS_API_KEY set and not a placeholder, a sample trace reaches the ingest endpoint, no orphan auto-roots) and prints a pass/fail report with a one-line remediation per failed check. Language-agnostic; auto-detects Python (pip) vs TypeScript (npm) vs Go (go list) project. Use this whenever a wizard finishes, or when "is it working" is the question.
metadata:
  author: neatlogs
  language: any
---

# NeatLogs — Post-instrumentation sanity check

Run this **after** any `neatlogs-py-*` / `neatlogs-ts-*` / `neatlogs-go` wizard, or
whenever the question is "is the SDK wired up and exporting?".

This is a read-only checker. It does not edit code, install packages, or call
the SDK. It inspects the project and reports.

## When to use this

- Just finished a wizard and want to confirm the steps landed.
- Tracing looks broken (no spans in the dashboard, "missing traces" report).
- Migrating between SDK versions and want to confirm the import survived.
- Onboarding a new contributor who touched the entry point.

**Not** the right tool for: choosing what to instrument (use the per-stack
wizard), or for SDK reference material (use `neatlogs-py` / `neatlogs-ts`).

## Step 1 — Detect the language

```bash
# Look at the top-level project files to pick which checks to run.
ls pyproject.toml requirements*.txt setup.py 2>/dev/null | head -1
ls package.json pnpm-lock.yaml yarn.lock package-lock.json 2>/dev/null | head -1
ls go.mod 2>/dev/null
```

| Project marker | Detected stack | Checks to run |
|---|---|---|
| `pyproject.toml` / `requirements*.txt` / `setup.py` | Python | 1A, 2A, 3A, 4A, 5A |
| `package.json` | TypeScript / Node | 1B, 2B, 3B, 4B, 5B |
| `go.mod` | Go | 1C, 2C, 3C, 4C, 5C |
| multiple | Run each detected path's checks | (suffix A/B/C) |

If none of these match, stop — this skill only validates the supported SDKs.

## Step 2 — Run the 5-check checklist

The checks below are language-specific. Use the row that matches the
detected stack. Each check has a **what it looks for**, a **how to run it**,
and a **one-line fix** if it fails.

### Check 1 — SDK is in the dependency manifest

**What it looks for**: the `neatlogs` package is actually declared, not just
imported ad-hoc (an ad-hoc import breaks upgrades and CI).

**Python**
```bash
grep -E '^\s*neatlogs(\s*[=><~]|$)' pyproject.toml requirements*.txt setup.py 2>/dev/null \
  || pip show neatlogs 2>/dev/null | head -1
```
**Fix**: `pip install --upgrade neatlogs` (or `uv add neatlogs` / `poetry add neatlogs@latest`).

**TypeScript**
```bash
node -e "const p=require('./package.json'); console.log(p.dependencies?.neatlogs ?? p.devDependencies?.neatlogs ?? 'NOT INSTALLED')"
```
**Fix**: `npm install neatlogs@latest` (or pnpm/yarn/bun equivalent).

**Go**
```bash
grep '^require github.com/neatlogs/neatlogs-go' go.mod || echo "NOT INSTALLED"
```
**Fix**: `go get github.com/neatlogs/neatlogs-go`.

### Check 2 — `init()` is called at process start

**What it looks for**: exactly one call to `init()` / `Init()` in the entry
module, **before** any other neatlogs API call and **before** any LLM SDK
import (the auto-instrumentation path is order-sensitive in Python).

**Python** — `grep` the entry module:
```bash
# Heuristic: the entry module is the file under if __name__ == "__main__":
# or the one referenced by the main CLI command. Replace `entry.py`
# with the actual file.
ENTRY=$(git grep -lE 'if __name__ == .__main__' -- '*.py' 2>/dev/null | head -1)
[ -n "$ENTRY" ] && echo "--- $ENTRY ---" \
  && grep -nE 'neatlogs\.init\(' "$ENTRY" \
  && echo "--- imports before init (BAD) ---" \
  && grep -nE '^(from|import) (openai|anthropic|google|groq|cohere|langchain|crewai|dspy|agno|google\.adk|strands|hermes|fastapi|flask)' "$ENTRY" | head -5
```
The second grep is the failure mode: an LLM SDK imported **above** `init()`
means auto-instrumentation is silently disabled.

**Fix**: move `neatlogs.init(...)` above the offending `import`/`from` line
in the entry module, or refactor so LLM SDKs are imported in a helper
module that's loaded after init.

**TypeScript** — `init()` MUST be `await`ed (the common bug is forgetting
the await):
```bash
# Find the entry, then check init is called AND awaited.
grep -nE 'await\s+init\s*\(' src/index.ts src/main.ts app/$(ls app 2>/dev/null | head -1) 2>/dev/null
```
**Fix**: `const { init } = await import('neatlogs'); await init({...});` at the
very top of the entry, before any other LLM SDK import. For Next.js, init
goes in `instrumentation.ts` via a **dynamic** `await import('neatlogs')`
inside `register()` (a static top-level import 500s on `Can't resolve 'crypto'`).

**Go** — `Init` must be the very first SDK call, and `defer shutdown(ctx)` must
sit right after it:
```bash
grep -nE 'neatlogs\.Init\(' main.go 2>/dev/null
grep -nE 'defer\s+shutdown' main.go 2>/dev/null
```
**Fix**: move `Init` above all LLM SDK usage; add `defer shutdown(ctx)`
immediately after the error check.

### Check 3 — `NEATLOGS_API_KEY` is set and not a placeholder

**What it looks for**: the API key is in the process env (or in `.env` if the
project uses one), AND it is not a literal placeholder like `your-key-here`,
`sk-xxx`, `nl-...`, or empty.

```bash
# In the current shell:
[ -n "$NEATLOGS_API_KEY" ] && echo "OK ($(echo "$NEATLOGS_API_KEY" | head -c 6)...)" \
  || echo "MISSING: NEATLOGS_API_KEY not in env"

# In .env, if present:
if [ -f .env ]; then
  KEY=$(grep -E '^NEATLOGS_API_KEY=' .env | cut -d= -f2-)
  case "$KEY" in
    ""|your-key-here|sk-xxx|REPLACE_ME|CHANGE_ME)
      echo "BAD: .env has placeholder value"
      ;;
    *)
      [ -n "$KEY" ] && echo "OK (.env)"
      ;;
  esac
fi
```
**Fix**: get a real key from the NeatLogs dashboard (Settings → API keys),
write it to `.env` as `NEATLOGS_API_KEY=<value>`, and make sure `.env` is in
`.gitignore` (it usually should be — verify with `git check-ignore .env`).

### Check 4 — A sample trace reaches the ingest endpoint

**What it looks for**: making one real call to the NeatLogs ingest endpoint
succeeds (HTTP 2xx), proving the project is configured end-to-end (key
accepted, network reachable, not firewalled).

This check needs to run from inside the project's runtime, so the wizard
runs a tiny one-shot:

**Python**
```python
# In a Python REPL or `python -c '...'`:
import os, sys
import neatlogs
neatlogs.init(api_key=os.environ["NEATLOGS_API_KEY"], workflow_name="neatlogs-validate-probe")
@neatlogs.span(kind="CHAIN")
def probe(): return "ok"
print(probe())
neatlogs.flush()
neatlogs.shutdown()
```
Expect: a trace named `probe` appears in the NeatLogs dashboard within
~10s. If `flush()` raises or the dashboard is empty, the key, network, or
backend URL is wrong.

**TypeScript**
```typescript
// In a Node REPL or `node -e '...'` after `await init(...)`:
import { span, flush, shutdown } from "neatlogs";
const probe = span({ kind: "CHAIN" }, async () => "ok");
await probe();
await flush();
await shutdown();
```

**Go**
```go
// After Init:
ctx, sp, end := neatlogs.Trace(ctx, "probe")
defer end()
sp.End()  // or whatever the close call is in your SDK version
_ = shutdown(ctx)
```

**Fix if the probe fails**:
- HTTP 401/403 → key wrong or revoked; regenerate in the dashboard.
- HTTP 4xx other than 401 → wrong backend URL; check `endpoint=` (Python) /
  `endpoint:` (TS) / `Endpoint` (Go) — default is the managed cloud, do not
  set unless self-hosting.
- Timeout / connection refused → firewall, corporate proxy, or `NEATLOGS_API_KEY`
  was set after the wizard's env step (re-source the env).
- Probe completes locally but the dashboard is empty → check
  `flush_interval` (Python/TS, default 5s); for Go, `defer shutdown(ctx)` is
  REQUIRED before process exit or the buffered spans never export.

### Check 5 — No orphan auto-roots from double-wrapping

**What it looks for**: the entry module does not call `init()` twice, AND no
LLM client is **both** wrapped and listed in `instrumentations=[]`. Double-
instrumentation produces duplicate spans in the dashboard (e.g. two LLM
spans for every chat completion).

**Python** — search for double init or instrumentations/wrap mix:
```bash
ENTRY=$(git grep -lE 'if __name__ == .__main__' -- '*.py' 2>/dev/null | head -1)
[ -n "$ENTRY" ] && grep -cE 'neatlogs\.init\(' "$ENTRY"   # should be 1
grep -rnE 'neatlogs\.wrap\(' . --include='*.py' 2>/dev/null
grep -rnE 'instrumentations=\[.*openai' . --include='*.py' 2>/dev/null
```
**Fix**: delete the second `init()` (it is a no-op + warning anyway), or
remove the client from `instrumentations=[]` if you also wrap it (the
`wrap()` path is preferred; auto-instrumentation is the fallback).

**TypeScript** — `instrumentations: [...]` in `init()` **THROWS**. The
`init({ instrumentations: ['openai'] })` pattern is wrong; use the per-
instance wrapper (`wrapOpenAI(new OpenAI())`).
```bash
grep -rnE "instrumentations:\s*\[" . --include='*.ts' 2>/dev/null
```
**Fix**: remove the `instrumentations` key, use `wrapOpenAI` /
`wrapAnthropic` / etc. at the client construction site.

## Step 3 — Report

Print the result as a pass/fail table. Format:

```
NeatLogs validation report
─────────────────────────
[OK]   1. SDK in deps          (Python, neatlogs 1.2.3)
[OK]   2. init() at start      (src/index.ts:12, awaited)
[FAIL] 3. API key set          (NEATLOGS_API_KEY present in .env but value is "your-key-here")
[OK]   4. Probe trace          (200 OK from /v1/traces; "probe" span visible in dashboard)
[OK]   5. No double-wrap       (no duplicate init, no instrumentations=[])

1 check failed. Fix: edit .env and replace the placeholder with a real key
from the NeatLogs dashboard (Settings → API keys). Re-run this skill after.
```

A clean run is all 5 checks OK. Stop there. The wizard's job ends when the
report prints. If the user wants to instrument more (different framework,
different language), they pick the matching wizard; this skill does not
extend coverage.

## Rules

- **Read-only.** The skill inspects; it does not edit. The only side effect
  is check 4's probe, which sends one span to the user's own project. Make
  that clear before running.
- **No SDK upgrade.** If check 1 finds the SDK missing, do not install it
  silently. Tell the user to install and re-run.
- **No key check via network probe.** Check 3 reads env, it does not call
  the NeatLogs API. The probe in check 4 is the only network call.
- **Concrete fixes.** Each `Fix:` must be a specific edit, not
  "investigate the dashboard". If the fix is more than one edit, point at
  the matching wizard, not at a step in this skill.

## Reference

- Per-stack instrumentation: pick the right `neatlogs-py-*` /
  `neatlogs-ts-*` / `neatlogs-go` skill.
- Common gotchas (import order, Pydantic-Settings crash, Next.js crypto
  build error): see `troubleshooting.md` in each per-stack skill. This
  skill is a checklist, not documentation.
