# Neatlogs AI Skills

AI agent skills for [Neatlogs](https://neatlogs.com) — the observability and tracing platform for LLM and AI agent applications.

These skills give your coding agent (Claude Code, Cursor, Codex, Windsurf, etc.) expert knowledge of the NeatLogs SDK so it can correctly instrument your code, set up tracing, and debug issues.

The public, language-neutral telemetry contract for SDK and integration compatibility lives in [`contracts/v2`](./contracts/v2/). Its manifest pins the exact schema digest and its golden fixtures lock multi-choice LLM output, assistant tool requests, separate linked and unlinked TOOL executions, and recovered-root semantics. Each runtime repository validates its own vendored copy before release.

The installed SDK Doctor output contract lives in [`contracts/doctor/v2`](./contracts/doctor/v2/). It defines credential-safe local and probe results without exposing internal service topology.

## Available skills

| Skill | Stack | Description |
|-------|-------|-------------|
| [`neatlogs-py`](./skills/neatlogs-py/) | Python | Instrument Python LLM apps with `neatlogs` — wrappers, decorators, spans, and framework integrations |
| [`neatlogs-ts`](./skills/neatlogs-ts/) | TypeScript / Node.js | Instrument TypeScript LLM apps with `neatlogs` — wrappers, handlers, hooks, processors, and custom spans |
| [`neatlogs-go`](./skills/neatlogs-go/) | Go | Instrument Go LLM apps with `neatlogs-go` — Gemini via `WrapGenAI`, direct/unsupported providers via explicit helpers, custom boundaries, and per-request identity |
| [`neatlogs-ingest`](./skills/neatlogs-ingest/) | Any other language | Send nested JSON to HTTP ingest (`POST /v1/trace`) or configure OTLP/gRPC when OpenTelemetry already exists |
| [`neatlogs-local-testing`](./skills/neatlogs-local-testing/) | Agent project / CLI | Create or resume experiments, choose fresh or existing cases, run actual agents and compare quality, tools and performance |
| [`neatlogs-public-api-cli`](./skills/neatlogs-public-api-cli/) | Public API / terminal | Read project traces and use the supported `neatlogs-cli` with project-scoped authorization |

## Local agent testing

Use `neatlogs-local-testing` to guide dataset selection, real agent runs, quality checks and comparisons. Supply your own goal; the skill does not prescribe a model or target. It asks whether to use an existing dataset or fresh cases when that choice is missing.

For the prerelease skill in this PR, install the selected release branch outside your project. The quoted source includes an explicit Git ref, including its slash-separated branch name:

```bash
npx skills add 'https://github.com/neatlogs/skills#shyam/local-testing-skill-20261104' --skill neatlogs-local-testing --agent codex -g
```

For an immutable release, replace that fragment with its reviewed commit SHA. After the skill is available on the default branch, the unpinned shorthand installs that branch:

```bash
npx skills add neatlogs/skills --skill neatlogs-local-testing --agent codex -g
# Claude Code: use --agent claude-code
```

The copied local-testing prompt can have your coding assistant check and install the skill for you. Copying text alone does not install anything. The assistant must read the installed `SKILL.md` before continuing; a new session is not needed for that explicit read. Keep browser sign-in approval separate from skill installation.

## Trace Codex sessions with `@neatlogs/codex`

These Agent Skills teach coding agents to instrument the application you are building. They do not trace the coding agent itself. To capture Codex coding sessions, install [`@neatlogs/codex`](https://github.com/neatlogs/neatlogs-codex), which registers Codex lifecycle hooks and exports those session traces to Neatlogs:

```bash
npm install -g @neatlogs/codex
neatlogs-codex setup --global --api-key YOUR_PROJECT_KEY
neatlogs-codex status --global
neatlogs-codex doctor --global
```

## Installation

### Recommended — works everywhere (Claude Code, Cursor, Codex, Windsurf, etc.)

Run this from your project folder. Requires Node.js:

```bash
npx skills add neatlogs/skills --skill "neatlogs-py"
```

The CLI auto-detects which agent you have installed and links the skill into its skills directory. Done.

For a global install (available in every project):

```bash
npx skills add neatlogs/skills --skill "neatlogs-py" -g
```

To target a specific agent explicitly:

```bash
npx skills add neatlogs/skills --skill "neatlogs-py" --agent "claude-code"
npx skills add neatlogs/skills --skill "neatlogs-py" --agent "cursor"
```

### Alternative — ask your coding agent

If you don't have Node.js, just ask your agent in chat:

> *"Install the NeatLogs AI skill from github.com/neatlogs/skills"*

The agent will clone the repo and link the skill itself.

### Claude Code — native plugin install

Claude Code (CLI, desktop, AND IDE extensions) supports installing this as a plugin. Two ways:

**A. Slash commands (Claude Code CLI / desktop only)**

```
/plugin marketplace add neatlogs/skills
/plugin install neatlogs-py@neatlogs
```

**B. GUI (Claude Code VSCode / JetBrains extension)**

Open the Claude Code panel, click **Manage Plugins** → **Marketplaces** tab → paste `https://github.com/neatlogs/skills` and click **Add**. Then switch to the **Plugins** tab and install `neatlogs-py`.

After either method, restart Claude Code when prompted. The plugin appears under **Plugins → Installed**.

### Alternative — manual git clone + symlink

```bash
git clone https://github.com/neatlogs/skills ~/neatlogs-skills

# Claude Code
mkdir -p ~/.claude/skills
ln -s ~/neatlogs-skills/skills/neatlogs-py ~/.claude/skills/neatlogs-py

# Cursor
mkdir -p ~/.cursor/skills
ln -s ~/neatlogs-skills/skills/neatlogs-py ~/.cursor/skills/neatlogs-py
```

## Where the skill is installed

| Agent | Project-level | Global |
|---|---|---|
| Claude Code | `.claude/skills/neatlogs-py/` | `~/.claude/skills/neatlogs-py/` |
| Cursor | `.agents/skills/neatlogs-py/` (or `.cursor/skills/`) | `~/.cursor/skills/neatlogs-py/` |
| Codex | `.agents/skills/neatlogs-py/` | `~/.codex/skills/neatlogs-py/` |
| Windsurf | `.windsurf/skills/neatlogs-py/` | `~/.codeium/windsurf/skills/neatlogs-py/` |

`.agents/skills/` is the [open-standard](https://agentskills.io) shared directory — Cursor, Codex, Windsurf, and several others all read from it.

## Verifying the install worked

Open your agent and ask any NeatLogs question:

> *"What's the difference between `@span` and `trace()` in neatlogs?"*

If the skill activated, the answer will reference NeatLogs-specific patterns — supported wrappers/handlers/hooks/processors as the sole capture owner, plus `@span(kind="...")` for custom orchestration. If the answer is generic, the skill didn't load — restart your agent or check the install path above.

## Updating

Skills installed via `npx skills add` (default symlink mode) or `git clone` auto-update on next agent restart after you pull the latest:

```bash
# CLI users
npx skills update

# Manual clone users
cd ~/neatlogs-skills && git pull

# Claude Code plugin users (CLI/desktop)
/plugin → Installed → click the refresh icon next to neatlogs-py

# Claude Code plugin users (IDE extension)
Manage Plugins → Marketplaces → click the refresh icon next to "neatlogs"
```

## What the skill does

Once installed, your coding agent automatically activates the skill when you ask anything related to NeatLogs:

> *"Add neatlogs tracing to my OpenAI calls"*
> *"Instrument my CrewAI agents with neatlogs"*
> *"Why is my wrapped LLM call producing duplicate spans?"*

The agent reads the skill documentation and follows correct integration patterns from the reference files inside the skill.

## Requirements

- A coding agent that supports the [Agent Skills](https://agentskills.io) standard — Claude Code, Cursor, Codex, Gemini CLI, Windsurf, OpenCode, Goose, etc.
- For `neatlogs-py`: Python ≥ 3.10 and `pip install neatlogs`
- For `neatlogs-ts`: Node.js ≥ 18 and `npm install neatlogs`

## Links

- [NeatLogs platform](https://neatlogs.com)
- [Python SDK on PyPI](https://pypi.org/project/neatlogs/)
- [Documentation](https://docs.neatlogs.com)
- [Agent Skills open standard](https://agentskills.io)

## License

MIT
