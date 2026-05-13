# NeatLogs AI Skills

AI agent skills for [NeatLogs](https://neatlogs.com) — the observability and tracing platform for LLM and AI agent applications.

These skills give your coding agent (Claude Code, Cursor, Codex, etc.) expert knowledge of the NeatLogs SDK so it can correctly instrument your code, set up tracing, and debug issues.

## Available skills

| Skill | Stack | Description |
|-------|-------|-------------|
| [`neatlogs-py`](./skills/neatlogs-py/) | Python | Instrument Python LLM apps with `neatlogs` — decorators, spans, prompt templates, framework integrations |

## Installation

### Ask your coding agent

The simplest method — no prerequisites needed.

> "Install the NeatLogs AI skill from github.com/neatlogs/skills"

Your agent will clone the repo and link the skill into its skills directory.

### Cursor plugin

```
/add-plugin neatlogs
```

### CLI (`npx skills add`)

Requires Node.js.

```bash
# Python skill
npx skills add neatlogs/skills --skill "neatlogs-py"
```

To target a specific agent directly:

```bash
npx skills add neatlogs/skills --skill "neatlogs-py" --agent "claude-code"
```

### Manual installation

```bash
# Clone the repo somewhere stable
git clone https://github.com/neatlogs/skills /path/to/neatlogs-skills

# Make sure your agent's skills dir exists
mkdir -p ~/.claude/skills

# Symlink the skill folder
ln -s /path/to/neatlogs-skills/skills/neatlogs-py ~/.claude/skills/neatlogs-py
```

Replace `~/.claude/skills` with your agent's skills directory:
- Claude Code: `~/.claude/skills/`
- Cursor: `~/.cursor/skills/`
- Codex: `~/.codex/skills/`

## Updating

Skills auto-update on next agent restart if installed via `npx skills add` (default symlink mode) or git clone.

```bash
# CLI users
npx skills update

# Manual install users
cd /path/to/neatlogs-skills && git pull
```

## What the skill does

After installation, your coding agent automatically activates the skill when you ask anything related to NeatLogs:

> *"Add neatlogs tracing to my OpenAI calls"*
> *"Instrument my CrewAI agents with neatlogs"*
> *"Why aren't my prompt templates showing up in the trace?"*

The agent will read the full skill documentation and follow correct integration patterns from the references files.

## Requirements

- **For the skill itself**: a coding agent that supports the [Agent Skills](https://agentskills.io) standard (Claude Code, Cursor, Codex, Gemini CLI, etc.)
- **For `neatlogs-py`**: Python ≥3.10 and `pip install neatlogs`

## Links

- [NeatLogs platform](https://neatlogs.com)
- [Python SDK on PyPI](https://pypi.org/project/neatlogs/)
- [Documentation](https://docs.neatlogs.com)
- [Open standard](https://agentskills.io)

## License

MIT
