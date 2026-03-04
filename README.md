# Motif

**Discover your coding patterns. Generate personalized AI rules.**

[![PyPI version](https://img.shields.io/pypi/v/motif-cli)](https://pypi.org/project/motif-cli/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

Motif reads your Cursor and Claude Code conversations, discovers your recurring patterns, and generates personalized `CLAUDE.md` / `.cursorrules` / skills files tuned to your actual working style.

No API key needed. No server. Your data stays on your machine.

![Motif Demo](demo.gif)

## Install

```bash
pip install motif-cli
```

## How It Works

1. **Extract** conversations from Cursor and/or Claude Code
2. **Analyze** — Motif prepares your data and your IDE's agent does the analysis (no external LLM calls)
3. **Generate** — turn analysis into CLAUDE.md, skills, and rules files routed to the right locations

## Quick Start

### Option A: Agent-driven (recommended)

If you use Cursor, install the Motif skill so your agent handles everything:

```bash
motif setup
```

Then just tell your agent: **"analyze my coding patterns"** — it handles extraction, analysis, and generation.

### Option B: Manual CLI

```bash
# Extract conversations from all available sources
motif extract all

# See what was extracted
motif list

# Prepare data for analysis (your agent reads the output)
motif analyze --prepare

# After your agent produces analysis JSON, generate config files
motif rules analysis-output.json

# Generate a summary report
motif report analysis-output.json
```

## Commands

### `motif extract`

Extract conversations from AI coding tools into `~/.motif/conversations/`.

```bash
motif extract cursor     # Extract from Cursor
motif extract claude     # Extract from Claude Code
motif extract all        # Extract from all sources
```

### `motif list`

Show all extracted projects with message counts and date ranges.

```bash
motif list
```

### `motif analyze`

Prepare extracted data for pattern analysis. The output is a markdown file containing your conversation data and analysis instructions — your IDE's agent reads it and follows the embedded prompt.

```bash
motif analyze --prepare                    # Analyze current project
motif analyze --prepare --project myapp    # Specify project
motif analyze --prepare --budget 50000     # Custom token budget
motif analyze --prepare --preview          # Preview session relevance scores
motif analyze --prepare --no-filter        # Skip relevance filtering
motif analyze --prepare --stats            # Show pipeline stats only
```

### `motif rules`

Parse analysis JSON output and generate configuration files (`CLAUDE.md`, skill files, `.cursorrules`).

```bash
motif rules analysis.json              # Generate to ~/.motif/generated/
motif rules analysis.json --dry-run    # Preview what would be generated
motif rules analysis.json --apply      # Deploy to project/user directories
```

### `motif report`

Generate a summary report from analysis output.

```bash
motif report analysis.json                     # Markdown report
motif report analysis.json --output report.md  # Custom output path
```

### `motif setup`

Install the `motif-analyze` Cursor skill for seamless agent integration.

```bash
motif setup
```

## What It Extracts

**Cursor IDE** — Reads `state.vscdb`, extracts user/assistant dialogue organized by project. Captures messages, file references, tool usage, and model info.

**Claude Code** — Reads `~/.claude/projects/` session files. Same structured output with session tracking.

## Example Output

The following was generated from a real developer's Claude Code history (386 messages across 33 sessions). This developer builds a multiplayer game using AI as their sole engineering tool — they design features and direct the AI, but don't write code themselves.

### Discovered Skills

**session-startup** — triggered 8+ times

> User says "refresh yourself", "we're working in [project] today", or "we shall continue"

1. Read project README, STATUS, MEMORY, and recent git log
2. Summarize: current phase, what's working, what's next
3. Wait for user direction before acting — do not propose work

**bug-fix-iteration** — triggered 30+ times

> User pastes error logs, console output, or says "it's still broken"

1. Read the pasted logs carefully — identify the exact error
2. Propose a targeted fix (don't refactor unrelated code)
3. Apply the fix
4. Ask user to test and report back

**deploy-production** — triggered 8+ times

> User says "deploy", "push to production", or "ship it"

1. cd to project root
2. Deploy server to Fly.io with --local-only flag
3. Deploy client from client/ subdirectory to Vercel
4. Verify both deployments succeeded

### Identified Rules

| Rule | What it enforces | Evidence |
|------|-----------------|----------|
| no-regressions | Never break existing functionality when adding new features | *"you broke the camera switching again"* |
| keep-it-simple | Solve the exact problem stated. Don't add features the user didn't ask for. | *"I just wanted to fix the button, not refactor the whole component"* |
| step-by-step | When manual action is required, provide numbered lists with exact commands. Don't explain theory. | *"just tell me what to type"* |
| no-log-flooding | Don't make changes that cause console log flooding. Add reconnection limits. | *"the logs are going crazy again"* |

### Communication Style

| Aspect | Pattern |
|--------|---------|
| Brevity | Terse and direct. 1-3 sentences, minimal punctuation, frequent lowercase. |
| Feedback | Reports results factually. Pastes logs when things break. Says "it works" when things work. |
| Corrections | Patient but persistent. Will paste logs repeatedly. Pushes back when AI goes in circles. |
| Proactivity | High. Expects the agent to execute rather than explain options. |

### Generated CLAUDE.md (excerpt)

```markdown
## Agent Behavior

### Rules

1. Never break existing functionality when adding new features.
2. Solve the exact problem stated. Don't add features the user didn't ask for.
3. Use refs for values accessed in callbacks/closures, not React state.
4. Never paste secrets in responses or store them insecurely.
5. When manual action is required, provide numbered lists with exact commands.
6. Don't make changes that cause console log flooding.
7. Follow the project's documented deployment process exactly.
8. Provide debug/test buttons for visual features so they can be tested in isolation.

## Workflow Triggers

| When you're... | Load this file |
|---|---|
| User says 'refresh yourself' or 'we shall continue' | session-startup/SKILL.md |
| User pastes error logs or says 'it's still broken' | bug-fix-iteration/SKILL.md |
| User says 'deploy' or 'ship it' | deploy-production/SKILL.md |
```

Full example output (analysis JSON, generated CLAUDE.md, skill files, report): [`examples/`](examples/)

## License

MIT
