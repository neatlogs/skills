# Step 1: Install neatlogs + check Pi Agent version

## 1. Install neatlogs

1. Call `detect_package_manager` to get the install command (npm/pnpm/yarn/bun).
2. Install the LATEST `neatlogs` — always pull the newest published version, do not pin an older one:
   - npm: `npm install neatlogs@latest`
   - pnpm: `pnpm add neatlogs@latest`
   - yarn: `yarn add neatlogs@latest`
   - bun: `bun add neatlogs@latest`
3. Maintained Pi 0.83 requires Node.js >= 22.19. Legacy Pi projects may support older Node versions.

`piAgentHooks` is self-contained — it needs no extra packages and no Pi plugin. It subscribes to the event API Pi already exposes.

## 2. Check the Pi Agent version (informational)

```bash
rg '@(earendil-works|mariozechner)/pi-' package.json
npm ls @earendil-works/pi-agent-core @mariozechner/pi-agent-core 2>/dev/null
```

Prefer maintained `@earendil-works/pi-agent-core` and `@earendil-works/pi-ai`; they are versioned together. Do not silently replace legacy packages during an instrumentation-only task, but report which family and version the project uses.

## 3. Both Pi packages are ESM-only

They are `"type": "module"` with no CommonJS build, so a CJS entry file fails to load them at all — `ERR_PACKAGE_PATH_NOT_EXPORTED` from `require`, before any neatlogs code runs. This is Pi's constraint, not a neatlogs one, but you will hit it while wiring up the instrumentation. If the project is CommonJS, the file that imports Pi must be ESM: either `"type": "module"` in `package.json`, or the `.mts` / `.mjs` extension on that file.

`neatlogs` itself ships both builds, so it imports either way.

Pi's public surface that neatlogs covers:

| Entry point | Traced by |
|---|---|
| `new Agent({...})` → prompts, queues, tools, abort, reset | `piAgentHooks(agent)` |
| `new AgentHarness({...})` → Agent runs, `compact`, `navigateTree` | `piAgentHooks(harness)` |
| `agentLoop` / `agentLoopContinue` (return an `EventStream`) | `tracePiAgentEvents()` — see `references/low-level-api.md` |
| `runAgentLoop` / `runAgentLoopContinue` (take an event sink) | `tracePiAgentEvents()` — see `references/low-level-api.md` |
| a bare `streamFn` (`streamProxy`, `streamSimple`) called outside any loop | `tracePiStream()` — see `references/low-level-api.md` |

## Verification

- `neatlogs` appears in `package.json` dependencies.
- Pi Agent version noted, and you know which entry point(s) the project actually uses.
