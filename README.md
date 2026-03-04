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

See [`examples/`](examples/) for a sample of what Motif generates from real conversation data — including a generated CLAUDE.md, skill files, and analysis report.

## Validated

Tested on three real-world datasets with zero false positives:

| Dataset | Messages | Skills Found | Rules Found | Profile |
|---------|----------|-------------|-------------|---------|
| Strategy/outreach project | 1,067 | 6-8 | 10 | Structured, proactive |
| Pure coding project | 218 | 4 | 6 | Technical, selective |
| External user (Claude Code) | 386 | 5 | 8 | Terse, delegates fully |

## Roadmap

- [x] `motif extract` — Cursor + Claude Code extraction
- [x] `motif list` — Project listing with merge detection
- [x] `motif analyze --prepare` — Data pipeline with relevance filtering
- [x] `motif rules` — Generate config files from analysis
- [x] `motif report` — Summary report generation
- [x] `motif setup` — Cursor skill installation
- [ ] `motif analyze --all` — Cross-project analysis
- [ ] `motif import` — Bring your own JSON/JSONL data
- [ ] `motif export` — JSON/markdown/text export
- [ ] `motif badge` — Static SVG for READMEs
- [ ] PDF report generation

## License

MIT
