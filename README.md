# NeatLogs AI Skills

AI agent skills for [NeatLogs](https://neatlogs.com) — the observability and tracing platform for LLM and AI agent applications.

These skills give your coding agent (Claude Code, Cursor, Codex, Windsurf, etc.) expert knowledge of the NeatLogs SDK so it can correctly instrument your code, set up tracing, and debug issues.

## Available skills

| Skill | Stack | Description |
|-------|-------|-------------|
| [`neatlogs-py`](./skills/neatlogs-py/) | Python | Instrument Python LLM apps with `neatlogs` — decorators, spans, prompt templates, framework integrations |

## Installation

Pick the method that fits your workflow.

### 1. Ask your coding agent (no prerequisites)

Open Claude Code, Cursor, or any agent that supports skills. Type:

> *"Install the NeatLogs AI skill from github.com/neatlogs/skills"*

The agent clones the repo and links the skill into its skills directory.

### 2. Claude Code plugin (native install)

Run these two slash commands inside Claude Code:

```
/plugin marketplace add neatlogs/skills
/plugin install neatlogs-py@neatlogs
```

Restart Claude Code when prompted. The plugin appears in `/plugin → Installed`.

### 3. CLI (`npx skills add`) — works for all agents

Requires Node.js. Run from your project folder:

```bash
npx skills add neatlogs/skills --skill "neatlogs-py"
```

Target a specific agent:

```bash
npx skills add neatlogs/skills --skill "neatlogs-py" --agent "claude-code"
npx skills add neatlogs/skills --skill "neatlogs-py" --agent "cursor"
```

Install globally (available in every project):

```bash
npx skills add neatlogs/skills --skill "neatlogs-py" -g
```

### 4. Manual git clone + symlink

```bash
git clone https://github.com/neatlogs/skills ~/neatlogs-skills

# For Claude Code
mkdir -p ~/.claude/skills
ln -s ~/neatlogs-skills/skills/neatlogs-py ~/.claude/skills/neatlogs-py

# For Cursor
mkdir -p ~/.cursor/skills
ln -s ~/neatlogs-skills/skills/neatlogs-py ~/.cursor/skills/neatlogs-py
```

## Where the skill is installed

The `npx skills add` command installs into one of these directories (first match wins):

| Agent | Project-level | Global |
|---|---|---|
| Claude Code | `.claude/skills/neatlogs-py/` | `~/.claude/skills/neatlogs-py/` |
| Cursor | `.agents/skills/neatlogs-py/` (or `.cursor/skills/`) | `~/.cursor/skills/neatlogs-py/` |
| Codex | `.agents/skills/neatlogs-py/` | `~/.codex/skills/neatlogs-py/` |
| Windsurf | `.windsurf/skills/neatlogs-py/` | `~/.codeium/windsurf/skills/neatlogs-py/` |

`.agents/skills/` is the [open-standard](https://agentskills.io) shared directory — Cursor, Codex, and several others all read from it.

## Updating

Skills installed via `npx skills add` (default symlink mode) or `git clone` auto-update on next agent restart after you pull the latest:

```bash
# CLI users
npx skills update

# Manual clone users
cd ~/neatlogs-skills && git pull

# Claude Code plugin users
/plugin → Installed → click the refresh icon next to neatlogs-py
```

## What the skill does

Once installed, your coding agent automatically activates the skill when you ask anything related to NeatLogs:

> *"Add neatlogs tracing to my OpenAI calls"*
> *"Instrument my CrewAI agents with neatlogs"*
> *"Why aren't my prompt templates showing up in the trace?"*

The agent reads the full skill documentation and follows the correct integration patterns from the references files.

## Requirements

- A coding agent that supports the [Agent Skills](https://agentskills.io) standard (Claude Code, Cursor, Codex, Gemini CLI, Windsurf, OpenCode, Goose, etc.)
- For `neatlogs-py`: Python ≥ 3.10 and `pip install neatlogs`

## Links

- [NeatLogs platform](https://neatlogs.com)
- [Python SDK on PyPI](https://pypi.org/project/neatlogs/)
- [Documentation](https://docs.neatlogs.com)
- [Agent Skills open standard](https://agentskills.io)

## License

MIT
