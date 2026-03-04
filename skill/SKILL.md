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

If not installed, tell the user:

- **Production:** `pip install motif-cli`
- **Development (local):** `pip install -e .` from the motif-cli directory

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

### 6. Generate Configuration

When the user approves, generate TWO things:

#### A. Update CLAUDE.md

**IMPORTANT: Check if CLAUDE.md already exists in the project root.**

**If CLAUDE.md exists:**
1. Read the existing file
2. **Merge** new rules into the existing content — do NOT overwrite or remove existing sections
3. Add a new section (or update existing section) called `## Motif-Discovered Rules` with the approved rules
4. Add/update a `## Communication Style` section with the style profile
5. Add/update a `## Workflow Triggers` table pointing to any generated skill files
6. Preserve ALL existing content — project overview, architecture docs, existing rules, etc.
7. Add a comment at the top of the Motif section: `<!-- Generated by Motif v0.1.0 — review and customize -->`

**If CLAUDE.md does NOT exist:**
1. Create a new CLAUDE.md with:
   - Project context section (from analysis)
   - Communication style section
   - Motif-discovered rules section
   - Workflow triggers table
2. Add header: `<!-- Generated by Motif v0.1.0 — review and customize -->`

**Do NOT create .cursorrules** — Cursor reads CLAUDE.md, so one file is sufficient.

#### B. Generate Skill Files

For each approved skill, create a `.cursor/skills/[skill-name]/SKILL.md` file:

- 20-40 lines
- Include: trigger phrases, step-by-step workflow, key constraints from evidence
- These are outlines — the user will review and deepen them
- Add header: `<!-- Generated by Motif v0.1.0 — review and customize -->`

---

## Error Handling

| Situation | Response |
|-----------|----------|
| motif not installed | Give install instructions: `pip install motif-cli` or `pip install -e .` |
| No conversations found | "You need some Cursor/Claude Code conversation history first. Use your AI assistant for a while and try again." |
| Prepared file too large | "The analysis data is very large. Running with a smaller budget: `motif analyze --prepare --budget 40000`" |
| Fewer than 20 user messages | "Limited data available. Analysis may be thin. Consider accumulating more conversation history." |

---

## Important Rules

- **Do NOT skip the extraction step** — data may have changed since last run
- **Do NOT modify the prepared data file** — read it only
- **Lead with summary and context** — the user may not know what Motif is
- **Show evidence for every rule** — quote the user's own words, cite frequency
- **Let the user choose** what to generate — don't auto-generate
- **Merge into existing CLAUDE.md** — never overwrite existing project documentation
- **Only generate CLAUDE.md** — do not create separate .cursorrules files
- **Generated skill files** — 20-40 lines, outlines not full implementations
