# Step 1: Install neatlogs

1. Call `detect_package_manager` for the install command.
2. Install the LATEST `neatlogs` (npm: `npm install neatlogs@latest`, pnpm: `pnpm add neatlogs@latest`, yarn: `yarn add neatlogs@latest`, bun: `bun add neatlogs@latest`). Always pull the latest published version — do not pin an older one.
3. Node.js >= 18 is sufficient for AI SDK v6. AI SDK v7 and `@ai-sdk/otel` require Node.js >= 22.
4. `neatlogs` installs `@ai-sdk/otel` automatically as an optional dependency. If the project disables optional dependencies, install `@ai-sdk/otel@^1` explicitly before using AI SDK v7 telemetry.

`neatlogs` appears in `package.json`. Proceed.
