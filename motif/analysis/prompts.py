"""
Analysis prompt for Motif CLI.

Contains the core prompt that instructs the host agent (Cursor/Claude Code)
what to look for when analyzing conversation data.
"""


def get_prompt_version() -> str:
    """Return the version string for this prompt."""
    return "0.1.0"


def get_analysis_prompt() -> str:
    """Return the full analysis prompt for the host agent."""
    return """---

## Analysis Instructions

You are analyzing AI coding assistant conversation history to discover the user's patterns, workflows, and preferences. Your goal is to surface actionable insights that can be turned into Cursor skills, rules, and personalized guidance.

### What to discover

1. **Recurring workflows / skills** (3+ occurrences)
   - Look for: trigger phrases, consistent step sequences, repeated file paths
   - Rate confidence: high (5+ occurrences), medium (3-4), low (2)
   - Only recommend skills for patterns that repeat meaningfully

2. **Correction-derived rules**
   - Where the user pushes back on agent output
   - "don't do X", explicit instructions, user rewrites
   - These reveal implicit preferences and constraints

3. **Communication style**
   - Terse vs detailed, structured feedback patterns, correction style
   - Proactivity expectations (does the user want the agent to anticipate or wait for instructions?)

4. **Session-level patterns**
   - How sessions start and end
   - Rituals (e.g., always deploys at end, always refreshes on project state)

5. **Improvement areas**
   - Repeated corrections on same issue = missing rule
   - "Did you actually check X?" = missing verification step

6. **Project context**
   - What is this project, key entities, tools used

7. **Scope classification** (IMPORTANT)
   - For every skill and rule, classify its scope as `"project"` or `"user"`.
   - **project**: References specific file paths, deployment targets, project-specific tools/services, tech stack, domain entities. Only useful inside this codebase.
   - **user**: Communication preferences, session rituals, general coding habits, correction patterns not tied to a specific codebase. Useful across all projects.
   - Include a `scope_reason` explaining the classification.
   - When analyzing data from multiple projects (`--all` mode), patterns appearing across 3+ projects are strong `user` signals. Patterns only in one project default to `project`.
   - When analyzing a single project, use content analysis: does it reference project-specific entities?

### What NOT to do

- Don't impose rigid categories; let the data drive the structure
- Don't recommend skills for one-off occurrences
- Don't generate complete skill files — just name + trigger + 3-5 step outline
- Don't recommend skills for things too varied to templatize

### Data notes

- **Pasted data:** Some messages contain pasted data (profiles, email threads, JSON) below the user's instruction. Focus on the instruction, not the pasted data.
- **Minimum data:** If fewer than 20 user messages are available, note that findings may be thin and recommend the user accumulate more conversation history.

### Output format

Respond with valid JSON in this structure:

```json
{
  "skills": [
    {
      "name": "string",
      "trigger": "string",
      "steps": ["step1", "step2", "..."],
      "evidence": ["quote or summary from conversation"],
      "confidence": "high|medium|low",
      "frequency": "string",
      "scope": "project|user",
      "scope_reason": "string"
    }
  ],
  "rules": [
    {
      "name": "string",
      "enforces": "string",
      "evidence": ["quote or summary"],
      "confidence": "high|medium|low",
      "scope": "project|user",
      "scope_reason": "string"
    }
  ],
  "communication_style": {
    "brevity": "string",
    "feedback_pattern": "string",
    "correction_style": "string",
    "proactivity_expectation": "string"
  },
  "session_patterns": {
    "startup": "string",
    "wrapup": "string",
    "evidence": ["quote or summary"]
  },
  "improvement_areas": [
    {
      "problem": "string",
      "evidence": ["quote or summary"],
      "proposed_rule": "string"
    }
  ],
  "project_context": {
    "description": "string",
    "key_entities": ["string"],
    "tools_used": ["string"]
  }
}
```
"""
