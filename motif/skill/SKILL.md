---
name: motif-analyze
description: Analyze AI coding conversation history to discover patterns, generate personalized CLAUDE.md rules and Cursor skills. Use when the user says "analyze my coding patterns", "generate rules for me", "personalize my AI", "what are my coding patterns", "create rules from my history", or "motif analyze".
---

# Motif Analyze

Discover coding patterns from your Cursor and Claude Code conversations. Update your `CLAUDE.md` with personalized rules and generate Cursor skill files.

## When to Use

- "analyze my coding patterns"
- "generate rules for me"
- "personalize my AI"
- "what are my coding patterns"
- "create rules from my history"
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

### 2. Extract & Select Project

First, extract conversations:

```bash
motif extract all
```

**Error:** If no conversations found -> "You need some Cursor/Claude Code conversation history first. Use your AI assistant for a while and try again."

Then, check what projects are available:

```bash
motif list
```

Now, determine the current workspace name (last component of the workspace path — e.g., if workspace is `c:\Users\avivs\Documents\steam_page_analyst`, the name is "steam_page_analyst").

Use the **AskQuestion** tool to let the user choose which project to analyze. Build options as follows:

1. **ALWAYS include "This project ([current workspace name])" as the first option** — even if it doesn't appear in `motif list` output (the user may not have enough history yet, but they still want to try)
2. **"All projects combined"** — analyze everything together
3. **One option per additional project** from `motif list` output — but only projects OTHER than the current workspace (don't duplicate it)
4. **Do NOT include "unknown"** as an option — that's a data artifact, skip it

If the user already specified a project in their original request (e.g., "analyze my patterns for journey-map-makers"), skip the question and use that project.

**Remember the user's choice** — you'll use it in step 3.

**If the chosen project has no data:** After running `motif analyze --prepare`, if it reports 0 scoped messages, tell the user: "No conversation history found for [project]. You need to use your AI assistant in this workspace for a while first, then try again."

### 3. Prepare Analysis Data

Based on the user's choice from step 2, run:

**For a specific project:**
```bash
motif analyze --prepare --project <name>
```

**For all projects combined (omit --project):**
```bash
motif analyze --prepare
```

The command prints the path to the prepared output file. **Read that file** using the Read tool.

**Error:** If prepared file is very large -> "The analysis data is very large. Running with a smaller budget: `motif analyze --prepare --budget 40000`"

**Warning:** If fewer than 20 user messages -> "Limited data available. Analysis may be thin. Consider accumulating more conversation history."

### 4. Analyze the Data

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

### 5. Present Findings to User

Present your findings in this specific format. The user may not know what Motif is or what this output means, so lead with context and a summary.

**Format to follow:**

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

**2. [rule name]**
...

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

### 6. Search for Existing Skills (NEW STEP)

Before generating skills from scratch, search for high-quality existing skills that match the discovered patterns.

**For each skill identified in the analysis:**

1. **Search trusted repositories** using web search or WebFetch:
   - Search `https://github.com/sickn33/antigravity-awesome-skills/tree/main/skills/` for skills matching the pattern name
   - Try variations: if the skill is "deploy-production", search for "deployment", "deploy", "ci-cd"
   - Also check: `https://github.com/vercel-labs/agent-skills/`, `https://github.com/anthropics/skills/`

2. **Evaluate matches:**
   - If a matching skill is found with >70% conceptual overlap, fetch its raw SKILL.md content
   - Fetch via: `https://raw.githubusercontent.com/{owner}/{repo}/main/skills/{skill-name}/SKILL.md`
   - Note: these are MIT licensed, safe to adapt

3. **Record search results** for each skill:
   - Found match: save the URL and note "adapt from {source}"
   - No match: note "generate from scratch"

**Skip this step if:** the user explicitly asks to skip search, or if web search tools are unavailable.

### 7. Generate Configuration (via Subagents)

When the user approves generation, use **parallel subagents** for speed and quality.

#### A. Update CLAUDE.md (main agent handles this directly)

**IMPORTANT: Check if CLAUDE.md already exists in the project root.**

**If CLAUDE.md exists:**
1. Read the existing file
2. **Merge** new rules into the existing content — do NOT overwrite or remove existing sections
3. Add a new section (or update existing section) called `## Motif-Discovered Rules` with the approved rules
4. Add/update a `## Communication Style` section with the style profile
5. Add/update a `## Workflow Triggers` table pointing to any generated skill files
6. Add a `## Pre-Completion Checklist` section from improvement areas
7. Add `### Subagent Delegation` under Agent Behavior:
   > Prefer delegating to subagents for complex, multi-step tasks. This prevents overloading the main context window and improves quality.
   > **When to delegate:** Tasks with 3+ distinct steps, research-heavy work, parallel workstreams, skill file generation.
   > **Model selection:** Use fast model for coding tasks and implementation. Use default model for planning and architecture.
8. Preserve ALL existing content — project overview, architecture docs, existing rules, etc.
9. Add a comment at the top of the Motif section: `<!-- Generated by Motif v0.2.0 -- review and customize -->`

**If CLAUDE.md does NOT exist:**
1. Create a new CLAUDE.md with all sections above
2. Add header: `<!-- Generated by Motif v0.2.0 -- review and customize -->`

**Do NOT create .cursorrules** — Cursor reads CLAUDE.md, so one file is sufficient.

#### B. Generate Skill Files (delegate to subagents)

**Read the quality bar first:** Read `motif/exemplars/QUALITY_BAR.md` (installed alongside motif) to understand the structural requirements.

**Read 1-2 exemplar skills** from `motif/exemplars/` to calibrate quality. Good exemplars:
- `motif/exemplars/brainstorming.md` — for procedural workflow skills
- `motif/exemplars/systematic-debugging.md` — for debugging/investigation skills
- `motif/exemplars/react-patterns.md` — for reference/patterns catalog skills

**For each approved skill, launch a subagent (fast model)** with this context:
1. The skill's analysis data (name, purpose, trigger, instructions, best practices, pitfalls, constraints, evidence)
2. One relevant exemplar skill as a quality reference
3. If a matching existing skill was found in step 6, include it with instruction: "Adapt this existing skill for the user's specific patterns"
4. The quality bar requirements from QUALITY_BAR.md
5. Instructions: "Create a `.cursor/skills/{skill-name}/SKILL.md` file. Target 80-200 lines. Match the exemplar's structural depth — sections, tables, decision points, hard gates where appropriate. Personalize with the user's evidence and constraints."

**Run up to 4 subagents in parallel.** Each subagent creates one skill file.

**Skill file requirements:**
- 80-200 lines (not the old 20-40 line skeletons)
- Must include: frontmatter, purpose/overview, when to use, instructions, best practices (if available), common pitfalls (if available), key constraints
- Add header: `<!-- Generated by Motif v0.2.0 -- review and customize -->`
- User-scoped skills go to `~/.cursor/skills/{skill-name}/SKILL.md`
- Project-scoped skills go to `.cursor/skills/{skill-name}/SKILL.md`

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

- **Do NOT skip the extraction step** — data may have changed since last run
- **Do NOT modify the prepared data file** — read it only
- **Lead with summary and context** — the user may not know what Motif is
- **Show evidence for every rule** — quote the user's own words, cite frequency
- **Let the user choose** what to generate — don't auto-generate
- **Merge into existing CLAUDE.md** — never overwrite existing project documentation
- **Only generate CLAUDE.md** — do not create separate .cursorrules files
- **Search before generating** — always check trusted repos for existing skills before creating from scratch
- **Use subagents for skill generation** — each skill file should be created by a subagent for quality and parallelism
- **Match the quality bar** — generated skills should be 80-200 lines with structured sections, not 20-line skeletons
- **Read exemplars first** — before generating, read at least one exemplar from motif/exemplars/ to calibrate quality
