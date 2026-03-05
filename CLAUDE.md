# CLAUDE.md

Guidance for AI agents working in the motif-cli repository.

## Project Overview

Motif is a CLI tool that reads Cursor and Claude Code conversations, generates a shareable "vibe report" showing how you work with AI, discovers recurring patterns, and produces personalized config files (CLAUDE.md, .cursorrules, skills).

- **Repo:** github.com/Bulugulu/motif-cli
- **PyPI:** pypi.org/project/motif-cli
- **Language:** Python 3.10+, Click CLI framework
- **Dependencies:** click, rich (minimal by design)

## Architecture

```
motif/
├── cli.py                  # All CLI commands (Click group)
├── config.py               # Paths, motif dir (~/.motif/)
├── store.py                # Load/save conversations from ~/.motif/conversations/
├── extractors/
│   ├── cursor.py           # Extract from Cursor IDE (state.vscdb)
│   └── claude_code.py      # Extract from Claude Code (~/.claude/projects/)
├── analysis/
│   ├── pipeline.py         # Relevance filtering, token budgeting, data prep
│   └── prompts.py          # Embedded analysis instructions for the host agent
├── report/
│   ├── metrics.py          # Quantitative metric computation (concurrency, growth, personality)
│   ├── html.py             # Self-contained HTML vibe report generation
│   └── markdown.py         # Markdown report from analysis JSON
├── rules/
│   └── generator.py        # Generate CLAUDE.md, .cursorrules, skill files from analysis
├── setup_cmd.py            # Install Cursor skill
└── skill/SKILL.md          # The Cursor skill that gets installed
```

## Release Workflow

**Version is in TWO places** — keep them in sync:
1. `pyproject.toml` → `version = "X.Y.Z"`
2. Parent repo changelog → `projects/vibe-coding-portfolio/CHANGELOG.md`

**To publish a new version:**
1. Bump version in `pyproject.toml`
2. Update changelog in parent Edtech repo
3. Commit and push
4. Tag: `git tag vX.Y.Z`
5. Push tag: `git push origin vX.Y.Z`
6. GitHub Actions (`.github/workflows/publish.yml`) auto-builds and publishes to PyPI

**When to bump version:**
- New commands or flags → minor bump (0.1 → 0.2)
- Bug fixes → patch bump (0.2.0 → 0.2.1)
- Docs-only changes don't require a release but can be bundled with one

## Documentation Updates

When adding features, update ALL of these:
- [ ] `README.md` — command docs, examples, screenshots if visual
- [ ] `llms.txt` — concise command listing for LLM consumption
- [ ] `examples/README.md` — if example output format changed
- [ ] Parent repo `CHANGELOG.md` — what changed and why

**README screenshots:** Taken with Playwright from the actual HTML report. Serve locally with `python -m http.server`, capture with `npx playwright screenshot` or Playwright's element screenshot API. Three section images: `vibe-report-hero.png`, `vibe-report-concurrency.png`, `vibe-report-personality.png`.

## Two-Repo Setup

This repo lives as a subpath inside the Edtech monorepo but has its own `.git`:
- **This repo** (motif-cli): code, README, llms.txt, pyproject.toml, screenshots
- **Parent repo** (Edtech): CHANGELOG.md at `projects/vibe-coding-portfolio/CHANGELOG.md`

Commits and pushes happen separately for each repo.

## Code Conventions

- CLI commands defined in `motif/cli.py` using Click decorators
- All commands are subcommands of the `cli` group (e.g., `@cli.command("vibe-report")`)
- Console output via `rich` — use `console.print()` with markup
- No external API calls — everything runs locally
- Extracted data stored in `~/.motif/conversations/` as JSON
- Reports written to `~/.motif/reports/`

## Tone

README and marketing copy should be punchy and use plain language. Avoid jargon — say "how many sessions you run in parallel" not "concurrency patterns." Lead with the question: "How good of a vibe coder are you?"
