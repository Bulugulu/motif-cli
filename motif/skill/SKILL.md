---
name: motif-analyze
description: Run Motif to generate your vibe report, launch the live dashboard, or personalize your CLAUDE.md and skills. Use when the user says "motif", "run motif", "vibe report", "generate my report", "motif live", "start the dashboard", "analyze my coding patterns", "personalize my AI", "generate rules for me", or "motif analyze".
---

# Motif

> Your AI coding companion. Discover how you work with AI — generate your vibe report, track your output live, or personalize your agent config.

## When to Use

- "motif" / "run motif"
- "vibe report" / "generate my report" / "generate my vibe report"
- "motif live" / "start the dashboard" / "live dashboard"
- "analyze my coding patterns" / "personalize my AI" / "generate rules for me"
- "motif analyze"

---

## Workflow (Execute in Order)

### 1. Check Prerequisites

Run in terminal:

```bash
motif --version
```

If the command is not found, fall back to `python -m motif --version`. If that also fails, tell the user to install: `pip install motif-cli`

**Use whichever invocation worked (`motif` or `python -m motif`) for all subsequent commands in this session.**

Next, check for updates:

```bash
motif update
```

If an update is available, the command will prompt the user to upgrade. **Let the user decide** — don't auto-upgrade. If they decline, continue with the current version. If they upgrade, re-verify with `motif --version` before proceeding.

### 2. Choose Your Action

**Ask the user what they'd like to do BEFORE extracting or running anything else.** Extraction can take a while, and some paths (Live Dashboard) don't need it at all.

If the user already specified what they want (e.g., "generate my vibe report"), skip asking and go directly to the corresponding path.

Present these options:

| Option | Description |
|---|---|
| **Vibe Report** | Generate your Agentic Coding Assessment — a shareable HTML report |
| **Live Dashboard** | Launch real-time AI productivity tracking in your terminal |
| **Personalize AI** | Analyze your patterns → update CLAUDE.md & generate skill files |

**How to present the options (platform-dependent):**

- **Cursor:** Use the `AskQuestion` tool:
  ```
  Title: "What would you like to do?"
  Questions: [{
    id: "action",
    prompt: "Choose a Motif feature:",
    options: [
      { id: "vibe_report", label: "Vibe Report — your Agentic Coding Assessment (shareable HTML)" },
      { id: "live_dashboard", label: "Live Dashboard — real-time AI productivity tracking" },
      { id: "personalize", label: "Personalize AI — discover patterns, update CLAUDE.md & generate skills" }
    ]
  }]
  ```

- **Claude Code / other agents:** Present the options as a numbered list in your response and ask the user to pick one. Wait for their reply before continuing.

Based on the user's choice, follow the corresponding path below.

---

### Path A: Vibe Report (if user chose `vibe_report`)

The key output of Motif — a self-contained HTML assessment of how you work with AI.

**What the CLI computes automatically:** Hero stats, agent concurrency, autonomy ratio, output density, growth scorecard, project constellation, and personality (frustration detection, catchphrases, swear counts via regex/heuristics).

**What you (the agent) add:** Qualitative analysis that makes the report personal — archetype, superpowers, communication style, growth narrative, notable moments, and blind spots. This requires reading a prepared data payload and producing a focused JSON.

#### A1. Extract Conversations

```bash
motif extract all
```

**Error:** If no conversations found -> "You need some Cursor/Claude Code conversation history first. Use your AI assistant for a while and try again."

#### A2. Prepare Data for Qualitative Analysis

Run the analysis pipeline with a small budget (qualitative analysis needs less data than full skills/rules analysis):

```bash
motif analyze --prepare --budget 20000
```

The command prints the path to the prepared output file. **Read that file** using the Read tool.

**If 0 scoped messages or fewer than 10 user messages:** Skip qualitative analysis — proceed directly to A4 and generate the report without it. Tell the user: "Not enough conversation history for qualitative analysis. Your report will include all quantitative metrics. Come back after more conversations for the full experience."

#### A3. Run Qualitative Analysis

The prepared output file contains conversation data and analysis instructions at the bottom. **Ignore the default analysis instructions** (those are for the full Personalize AI flow). Instead, follow these instructions:

Analyze the conversation data and produce a JSON with this exact structure:

```json
{
  "archetype": {
    "name": "2-4 word title (e.g., 'The Architect')",
    "description": "1-2 sentences explaining the archetype"
  },
  "superpowers": [
    {
      "name": "Short label (e.g., 'Decomposition')",
      "description": "1 sentence with evidence from conversations"
    }
  ],
  "communication_style": "2-3 punchy sentences. How they talk to AI.",
  "growth_narrative": "3-5 sentences. How they've evolved from early to recent sessions.",
  "notable_moments": [
    {
      "quote": "Exact or near-exact user quote (short, punchy)",
      "context": "1 sentence explaining when/why"
    }
  ],
  "blind_spots": [
    {
      "name": "Short label",
      "description": "1 sentence, framed as a growth opportunity"
    }
  ]
}
```

**Guidelines:**
- **Superpowers**: 2-3. Genuinely impressive, with evidence. Not generic compliments.
- **Notable moments**: 2-3 quotes that are funny, revealing, or show personality. Use actual words.
- **Blind spots**: 1-2. Honest but constructive.
- **Be specific**: "Leads with desired outcome in 1 sentence, adds constraints as bullets" beats "Terse communicator."
- **Keep it real**: This is a shareable report. Honest and specific > flattering and generic.

**Save the JSON** to `~/.motif/analysis/vibe-report-analysis-{YYYY-MM-DD}.json`.

**In Cursor:** You can delegate this analysis to a subagent (fast model) with the prepared data and the instructions above.
**In Claude Code:** Perform the analysis inline.

#### A4. Generate the Report

The vibe report uses all extracted projects by default — no project selection needed.

Build the command based on what's available:

```bash
# With qualitative analysis (recommended)
motif vibe-report --name "User Name" --analysis <path_to_analysis_json>

# Without qualitative analysis (quantitative only)
motif vibe-report --name "User Name"
```

The command outputs the path to the HTML file. Tell the user:
- **Where the file is** (the path printed by the command)
- **How to view it** — "Open this file in your browser to see your report"
- **It's shareable** — self-contained HTML, send it to anyone

**Done.** No further steps needed for this path.

---

### Path B: Live Dashboard (if user chose `live_dashboard`)

The real-time AI productivity tracker. No analysis needed — just launch it.

Tell the user:

```bash
motif live                    # Full TUI dashboard
motif live --compact          # Single-line compact display
motif live --summary          # Quick summary of current session
```

Explain:
- The dashboard tracks AIPM (AI tokens per minute), concurrency, and per-agent efficiency in real-time
- Currently supports Claude Code sessions; Cursor support coming via the VS Code extension
- Sessions are saved to `~/.motif/sessions/` with personal bests tracked

**Done.** No further steps needed for this path.

---

### Path C: Personalize AI (if user chose `personalize`)

The full analysis flow — discover coding patterns and generate personalized CLAUDE.md rules and skill files.

#### C1. Extract Conversations

```bash
motif extract all
```

**Error:** If no conversations found -> "You need some Cursor/Claude Code conversation history first. Use your AI assistant for a while and try again."

#### C2. Select Project

Run `motif list`:

```bash
motif list
```

Determine the current workspace name (last component of the workspace path — e.g., if workspace is `c:\Users\avivs\Documents\steam_page_analyst`, the name is "steam_page_analyst").

**Present project options to the user:**

Build the list as follows:
1. **ALWAYS include "This project ([current workspace name])" as the first option** — even if it doesn't appear in `motif list` output
2. **"All projects combined"** — analyze everything together
3. **One option per additional project** from `motif list` output (skip "unknown" — that's a data artifact)

**How to present (platform-dependent):**
- **Cursor:** Use the `AskQuestion` tool with the options above
- **Claude Code / other agents:** Present as a numbered list and wait for the user's choice

If the user already specified a project, skip asking.

#### C3. Check Previous Work

Run `motif status` to check for existing artifacts:

```bash
motif status --project <chosen_project>
```

Parse the output to determine:
- Whether an **analysis JSON** exists (and its date)
- Whether **skills/rules** have been generated before
- The **path to the analysis JSON** file (if it exists)

If a previous analysis exists, **ask the user** whether they want to:
- **Re-analyze** — run a fresh analysis (recommended if they've had many new conversations)
- **Regenerate from existing analysis** — skip re-analysis, just regenerate skills/rules from the last run

**How to present (platform-dependent):**
- **Cursor:** Use the `AskQuestion` tool
- **Claude Code / other agents:** Ask in text and wait for the reply

If no previous analysis exists, proceed directly to C4.

#### C4. Prepare Analysis Data

Based on the project choice:

**For a specific project:**
```bash
motif analyze --prepare --project <name>
```

**For all projects combined:**
```bash
motif analyze --prepare
```

The command prints the path to the prepared output file. **Read that file** using the Read tool.

**Error:** If prepared file is very large -> "The analysis data is very large. Running with a smaller budget: `motif analyze --prepare --budget 40000`"

**Warning:** If fewer than 20 user messages -> "Limited data available. Analysis may be thin. Consider accumulating more conversation history."

**If 0 scoped messages:** "No conversation history found for [project]. Use your AI assistant in this workspace for a while first, then try again."

#### C5. Analyze the Data

The prepared output file contains:
1. Conversation data (grouped by session)
2. **Analysis instructions** at the bottom (after `---` and `## Analysis Instructions`)

**Follow those analysis instructions carefully.** They tell you what patterns to look for:
- Recurring workflows / skills (3+ occurrences)
- Correction-derived rules
- Communication style
- Session-level patterns
- Improvement areas
- Project context

#### C6. Save Analysis JSON

After producing the analysis JSON, save it to a standardized location:

```
~/.motif/analysis/analysis-{safe_project}-{YYYY-MM-DD}.json
```

Where `{safe_project}` uses alphanumeric, hyphens, underscores — replace everything else with `_`.

#### C7. Present Findings to User

Present in this format. Lead with context — the user may not know what Motif is.

```
I ran a Motif analysis on your [N] conversations ([M] user messages) and here's what I found:

## Summary
- [X] skills to add (recurring workflows I can automate)
- [Y] rules to add to CLAUDE.md (preferences and constraints)
- [Z] improvement areas (things that keep going wrong)

## Fun facts about your coding style
- [1-3 interesting observations from communication_style or project_context.
  E.g., "You use structured numbered lists for feedback 80% of the time"
  or "You've referenced [entity] in 40% of your conversations"]

## Recommended Rules
For each rule, explain:

**1. [rule name]**
What it does: [enforces description]
Why you need it: [evidence — quote the user's own words when possible, cite frequency]

## Recommended Skills
For each skill:

**1. [skill name]** (triggered by: "[trigger phrase]", [frequency])
Steps: [3-5 step outline]
Evidence: [what conversations showed this pattern]

## Communication Style Profile
- Brevity: [description]
- Feedback pattern: [description]
- Correction style: [description]
- Proactivity expectation: [description]

## Improvement Areas
For each:
- Problem: [description]
- Evidence: [what keeps going wrong]
- Proposed fix: [rule or skill that would prevent it]

---

Should I generate your skills and update your CLAUDE.md?
```

**Critical:** End with the question. Do NOT auto-generate. Let the user confirm.

#### C8. Search for Existing Skills

Before generating skills from scratch, search for high-quality existing skills that match the discovered patterns.

**For each skill identified in the analysis:**

1. **Search trusted repositories** using web search or WebFetch:
   - `https://github.com/sickn33/antigravity-awesome-skills/tree/main/skills/`
   - Try variations: if the skill is "deploy-production", search for "deployment", "deploy", "ci-cd"

2. **Evaluate matches:**
   - If a matching skill with >70% conceptual overlap is found, fetch its raw SKILL.md content
   - Note: these are MIT licensed, safe to adapt

3. **Record search results** — found match: "adapt from {source}", no match: "generate from scratch"

**Skip this step if:** the user explicitly asks to skip, or if web search tools are unavailable.

#### C9. Generate Configuration

When the user approves, generate two things:

##### A. Update CLAUDE.md (you handle this — Motif never touches the user's file)

> **Motif never writes to the user's CLAUDE.md.** The `--apply` flag only deploys skill files. For CLAUDE.md, you (the agent) propose edits to the user's existing file. The generated reference is at `~/.motif/generated/CLAUDE.md`.

**If CLAUDE.md exists:**
1. Read the existing file in full
2. Read the generated reference from `~/.motif/generated/CLAUDE.md`
3. **Show the user** the specific edits you want to make — which sections to add/update, what content
4. **Wait for user approval** before making any edits
5. Use targeted edit operations — never rewrite the whole file
6. Sections to add/update:
   - `## Motif-Discovered Rules` — only rules the existing file doesn't already cover
   - `## Communication Style` — if not already present
   - `## Workflow Triggers` — add table entries for new skill files
7. Preserve ALL existing content
8. Add a comment: `<!-- Added by Motif -- review and customize -->`

**If CLAUDE.md does NOT exist:**
1. Show the user the generated reference and ask if they want you to create it
2. If yes, create a new CLAUDE.md based on the generated reference
3. Add header: `<!-- Generated by Motif -- review and customize -->`

**Do NOT create .cursorrules** — Cursor reads CLAUDE.md, so one file is sufficient.

##### B. Generate Skill Files (delegate to subagents when available)

**Read the quality bar first:** Read `motif/exemplars/QUALITY_BAR.md` to understand structural requirements.

**Read 1-2 exemplar skills** from `motif/exemplars/` to calibrate quality. Good exemplars:
- `motif/exemplars/brainstorming.md` — for procedural workflow skills
- `motif/exemplars/systematic-debugging.md` — for debugging/investigation skills
- `motif/exemplars/react-patterns.md` — for reference/patterns catalog skills

**For each approved skill:**
1. The skill's analysis data (name, purpose, trigger, instructions, best practices, pitfalls, constraints, evidence)
2. One relevant exemplar skill as a quality reference
3. If a matching existing skill was found in C8, include it with instruction: "Adapt this existing skill for the user's specific patterns"
4. The quality bar requirements from QUALITY_BAR.md
5. Create the skill file — target 80-200 lines

**In Cursor:** Launch up to 4 subagents in parallel (fast model), one per skill.
**In Claude Code / other agents:** Generate skill files sequentially.

**Skill file requirements:**
- 80-200 lines
- Must include: frontmatter (for Cursor), purpose/overview, when to use, instructions, best practices, common pitfalls, key constraints
- Add header: `<!-- Generated by Motif -- review and customize -->`

**Deployment paths (handled by `motif rules --apply`):**
- **Cursor:** User-scoped → `~/.cursor/skills/{skill-name}/SKILL.md`, Project-scoped → `.cursor/skills/{skill-name}/SKILL.md`
- **Claude Code:** User-scoped → `~/.claude/commands/{skill-name}.md`, Project-scoped → `.claude/commands/{skill-name}.md` (YAML frontmatter is stripped automatically)

If deploying manually (without `--apply`), write to the correct paths for the user's platform.

---

## Error Handling

| Situation | Response |
|-----------|----------|
| motif not installed | Give install instructions: `pip install motif-cli`, then use `motif` |
| No conversations found | "You need some Cursor/Claude Code conversation history first. Use your AI assistant for a while and try again." |
| Prepared file too large | "The analysis data is very large. Running with a smaller budget: `motif analyze --prepare --budget 40000`" |
| Fewer than 20 user messages | "Limited data available. Analysis may be thin. Consider accumulating more conversation history." |
| Web search unavailable | Skip search step, generate all skills from scratch using exemplars as quality reference |

---

## Important Rules

- **Lead with the user's intent** — if they said "vibe report", go straight to Path A. Don't force them through the full analysis flow.
- **Motif never writes to the user's CLAUDE.md** — `motif rules --apply` only deploys skill files. The generated CLAUDE.md at `~/.motif/generated/` is a reference only.
- **You (the agent) propose edits, not overwrites** — read existing CLAUDE.md, diff against generated reference, suggest targeted additions.
- **Always ask before editing CLAUDE.md** — present proposed changes and get explicit user confirmation.
- **Don't suggest rules that already exist** — the analysis pipeline includes existing CLAUDE.md content.
- **Run extraction in the paths that need it** (A and C) — data may have changed since last run. Path B (Live Dashboard) does not need extraction.
- **Do NOT modify the prepared data file** — read it only.
- **Always save analysis JSON** — after every full analysis, write it to `~/.motif/analysis/`.
- **Show evidence for every rule** — quote the user's own words, cite frequency.
- **Let the user choose** what to do — don't auto-generate, don't assume they want the full flow.
- **Do not create .cursorrules** — Cursor reads CLAUDE.md, so one file is sufficient.
- **Search before generating** — always check trusted repos for existing skills before creating from scratch.
- **Match the quality bar** — generated skills should be 80-200 lines with structured sections, not 20-line skeletons.
- **Read exemplars first** — before generating, read at least one exemplar from motif/exemplars/ to calibrate quality.
- **Platform-agnostic interaction** — when you need the user to make a choice, use `AskQuestion` in Cursor, or present a numbered list and wait in Claude Code / other agents.
