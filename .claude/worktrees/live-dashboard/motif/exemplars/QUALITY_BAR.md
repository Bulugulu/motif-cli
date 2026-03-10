# Skill Quality Bar

Distilled from [antigravity-awesome-skills SKILL_ANATOMY.md](https://github.com/sickn33/antigravity-awesome-skills/blob/main/docs/SKILL_ANATOMY.md).

Use this as the structural reference when generating skills. Every generated skill should meet the "Standard Skill" bar or higher.

## Skill Tiers

| Tier | Content | Sections |
|------|---------|----------|
| **Minimum Viable** | 100-200 words | Overview + Instructions |
| **Standard** | 300-800 words | Overview + When to Use + Instructions + Best Practices |
| **Comprehensive** | 800-2000 words | All sections + examples, tables, anti-patterns |

Motif-generated skills should target **Standard** tier minimum.

## Required Structure

### Frontmatter

```markdown
---
name: skill-name-in-kebab-case
description: "One-sentence summary under 200 characters"
---
```

### Sections (in order)

1. **Title (H1)** -- Clear, descriptive. Matches or expands the skill name.

2. **Overview / Purpose** -- 2-4 sentences. What this skill does and why it exists. What it prevents.

3. **When to Use** -- Bullet list of specific trigger conditions. Include "Use this ESPECIALLY when..." and "Don't skip when..." patterns where applicable.

4. **Instructions** -- The heart of the skill. Clear, actionable steps. Use:
   - Numbered steps for sequential workflows
   - Decision points ("If X, do Y; otherwise Z")
   - Hard gates where applicable ("Do NOT proceed until...")
   - Error handling ("If this fails...")

5. **Best Practices** -- Do/don't patterns. Use tables or bullet lists:
   ```
   | Do | Don't |
   |----|-------|
   | Fix at root cause | Patch symptoms |
   ```

6. **Common Pitfalls** -- What goes wrong and how to fix it:
   ```
   | Problem | Solution |
   |---------|----------|
   | Skipping investigation | Return to Phase 1 |
   ```

7. **Key Constraints** -- Non-negotiable rules for this workflow.

## Writing Guidelines

- **Use clear, direct language.** "Check if authenticated" not "You might want to consider checking..."
- **Use action verbs.** "Create the file" not "The file should be created"
- **Be specific.** "Run `npm test`" not "Run the tests"
- **Use tables** for comparisons, decision matrices, quick references
- **Use hard gates** for critical checkpoints that must not be skipped
- **Include red flags** -- signals the user/agent is doing it wrong

## Quality Checklist

Before finalizing a skill:

- [ ] Instructions are clear and actionable
- [ ] A beginner could follow this
- [ ] An expert would find it useful
- [ ] Non-obvious decisions are explained
- [ ] Edge cases are addressed
- [ ] Sections follow logical hierarchy
