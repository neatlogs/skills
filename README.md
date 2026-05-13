# Neatlogs AI Skills

AI agent skills for [Neatlogs](https://neatlogs.com) — the observability and tracing platform for LLM and AI agent applications.

These skills give your coding agent (Claude Code, Cursor, Codex, Windsurf, etc.) expert knowledge of the NeatLogs SDK so it can correctly instrument your code, set up tracing, and debug issues.

## Available skills

| Skill | Stack | Description |
|-------|-------|-------------|
| [`neatlogs-py`](./skills/neatlogs-py/) | Python | Instrument Python LLM apps with `neatlogs` — decorators, spans, prompt templates, framework integrations |

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

If the skill activated, the answer will reference NeatLogs-specific patterns — the `@span(kind="...")` decorator with kinds like `WORKFLOW`, `AGENT`, `TOOL`, prompt template tracking via `trace()`, and so on. If the answer is generic, the skill didn't load — restart your agent or check the install path above.

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
> *"Why aren't my prompt templates showing up in the trace?"*

The agent reads the skill documentation and follows correct integration patterns from the reference files inside the skill.

## Requirements

- A coding agent that supports the [Agent Skills](https://agentskills.io) standard — Claude Code, Cursor, Codex, Gemini CLI, Windsurf, OpenCode, Goose, etc.
- For `neatlogs-py`: Python ≥ 3.10 and `pip install neatlogs`

## Links

- [NeatLogs platform](https://neatlogs.com)
- [Python SDK on PyPI](https://pypi.org/project/neatlogs/)
- [Documentation](https://docs.neatlogs.com)
- [Agent Skills open standard](https://agentskills.io)

## License

MIT
