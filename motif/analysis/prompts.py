"""
Analysis prompt for Motif CLI.

Contains the core prompt that instructs the host agent (Cursor/Claude Code)
what to look for when analyzing conversation data.
"""


def get_prompt_version() -> str:
    """Return the version string for this prompt."""
    return "0.4.0"


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
   - For each skill, provide a rich outline:
     - `name`: kebab-case slug
     - `trigger`: when to activate
     - `purpose`: 1-2 sentences (why this skill exists, what it prevents)
     - `when_to_use`: specific trigger conditions including "especially when..." and "don't skip when..." patterns
     - `instructions`: 5-10 step-by-step instructions with decision points and error handling (not just 3-5)
     - `best_practices`: do/don't patterns observed from conversations
     - `common_pitfalls`: what goes wrong when workflow isn't followed (problem + solution)
     - `key_constraints`: non-negotiable rules for this workflow

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

8. **Existing CLAUDE.md awareness** (IMPORTANT)
   - If an `## Existing CLAUDE.md` section appears in this document, the user already has rules and configuration.
   - **Do NOT suggest rules that duplicate what already exists.** If an existing rule covers the same concern, skip it or suggest a refinement instead.
   - **Do NOT suggest skills that duplicate existing workflow triggers.** Check the existing CLAUDE.md for workflow trigger tables or skill references.
   - For rules that would enhance or refine existing ones, mark them with `"existing_overlap": "rule name or section it overlaps with"` and explain the delta.
   - Your output should be **additive** -- only new patterns the existing config doesn't already cover, or specific refinements to what's there.

### What NOT to do

- Don't impose rigid categories; let the data drive the structure
- Don't recommend skills for one-off occurrences
- Don't generate complete skill files -- provide structured outlines with purpose, instructions (5-10 steps), best practices, and pitfalls
- Don't recommend skills for things too varied to templatize
- Don't suggest rules that already exist in the user's CLAUDE.md (if provided)

### Data notes

- **Pasted data:** Some messages contain pasted data (profiles, email threads, JSON) below the user's instruction. Focus on the instruction, not the pasted data.
- **Minimum data:** If fewer than 20 user messages are available, note that findings may be thin and recommend the user accumulate more conversation history.
- **Existing CLAUDE.md:** If present in the prepared data, use it as context to avoid duplicating existing rules and to suggest targeted edits rather than a full rewrite.

### Output format

Respond with valid JSON in this structure:

```json
{
  "skills": [
    {
      "name": "string",
      "trigger": "string",
      "purpose": "string (why this skill exists, what it prevents)",
      "when_to_use": ["condition1", "condition2"],
      "instructions": ["step1 with decision points", "step2", "..."],
      "best_practices": ["do X because Y", "don't do Z because W"],
      "common_pitfalls": [{"problem": "string", "solution": "string"}],
      "key_constraints": ["non-negotiable rule 1"],
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


def get_vibe_report_prompt() -> str:
    """Return the analysis prompt for qualitative vibe report enrichment.

    Produces personality/narrative content grounded in assessment frameworks.
    No skills or rules -- that's a separate flow.
    """
    return """---

## Vibe Report Analysis Instructions

You are analyzing AI coding conversation history to produce **qualitative insights for a shareable vibe report**. This is NOT the full skills/rules analysis. Focus on how the user thinks, asks, learns, and grows through AI collaboration.

Read the conversation data above and produce a JSON following the schema below.

---

## Tone

**Default tone:** Concise, direct, blunt. Short sentences. No filler adjectives. State what the evidence shows. If something is mediocre, say it's mediocre. If there's not enough data for a claim, say so.

**For archetype descriptions, notable moment context, and blind spots:** Channel Terry Pratchett. Dry, absurd, observational. Describe mundane developer behavior with the gravity of cosmic events. Example: "He addressed the computer with the quiet authority of a man who has asked a machine to fix itself and been disappointed exactly the right number of times."

**Banned words/phrases:** impressive, remarkable, powerful, game-changer, next-level, crushing it, force to be reckoned with, powerhouse, showcases, demonstrates mastery, truly, incredible, a testament to. If you catch yourself reaching for a superlative, delete it and state the fact instead.

---

## Assessment Frameworks

Use these frameworks as structured lenses. Cite the framework by name when you reference it. Every claim must map to observable evidence in the conversations.

### Framework A: Bloom's Taxonomy (Cognitive Level of Prompts)

Classify user prompts by cognitive level. Lower levels = reckoning (AI-replaceable). Higher levels = judgment (human).

| Level | Name | Vibe Coding Examples |
|-------|------|---------------------|
| 1 | Remember | "fix this", "what does this error mean" |
| 2 | Understand | "explain how this works", "what's the difference between X and Y" |
| 3 | Apply | "use this pattern to refactor the auth module", "apply the same approach from file A" |
| 4 | Analyze | "why is this re-rendering? trace the state flow", "compare these two approaches" |
| 5 | Evaluate | "is this the right tradeoff? we gain X but lose Y", "should we use A or B given constraints?" |
| 6 | Create | "design a system for X with these constraints", "here's my spec, build this" |

Estimate where most of the user's prompts land. Cite example quotes at each observed level.

### Framework B: Vibe Coding Proficiency Rubric (6-Level)

Place the user on this spectrum with evidence.

| Level | Name | Observable Indicators |
|-------|------|----------------------|
| 1 | Novice | Prompts <50 words, no @mentions, "fix this" patterns, accepts AI output without checking |
| 2 | Beginner | Some context, occasional planning, single-agent, sometimes checks output |
| 3 | Intermediate | Uses @mentions, mentions testing, iterates with feedback, incremental approach |
| 4 | Proficient | Context engineering, plans before execution, considers edge cases, questions AI |
| 5 | Advanced | Multi-agent orchestration, blast radius thinking, creates rules/docs, discusses approaches |
| 6 | Expert | Socratic questioning of AI, systems thinking, builds reusable frameworks, teaches AI |

Sub-skills to assess: context engineering, prompt quality, planning, iteration strategy, blast radius thinking, multi-agent orchestration, Socratic questioning, rules creation, failure management.

### Framework C: Holistic Critical Thinking Rubric (4-Level)

| Level | Description | Text Indicators |
|-------|-------------|-----------------|
| Strong | Accurate interpretation, identifies salient arguments, evaluates alternatives, warranted conclusions | Questions assumptions, considers multiple perspectives, evidence-based reasoning |
| Acceptable | Acknowledges some alternatives, mostly unbiased interpretation | Some evaluation of options, generally sound reasoning |
| Unacceptable | Ignores alternatives, limited evaluation | Narrow focus, accepts first solution |
| Weak | Biased interpretation, fallacious reasoning, closed-minded | No alternative consideration, purely reactive |

Observable indicators:
- **Hypothesis formation:** "I think the issue is...", "my hypothesis is..."
- **Alternative consideration:** "another approach could be...", "what if we tried..."
- **Evidence evaluation:** "based on the error message...", "the logs show..."
- **Assumption questioning:** "wait, is that right?", "why does it do X?"

### Framework D: Metacognition Components

Three components -- look for evidence of each:

- **Metacognitive Knowledge** (awareness of own learning): "I learn better when...", "in my experience...", "I tend to make this mistake when..."
- **Metacognitive Monitoring** (checking own understanding): "I'm not sure about...", "let me check if I understand...", "wait, does that make sense?"
- **Metacognitive Control** (adjusting strategy): "that didn't work, let me try...", "I need to step back and rethink", "let's start over with a different strategy"

### Framework E: Judgment vs. Reckoning (Overarching Lens)

Reckoning = pattern recognition, prediction, data processing (what AI does well).
Judgment = context, ethics, values, navigating ambiguity (what humans must do).

Use this as the interpretive frame for the growth_narrative and blind_spots: is the user offloading reckoning to AI (good) or also offloading judgment (bad -- becoming a passive relay)?

---

## Output Format

Respond with valid JSON in this structure:

```json
{
  "archetype": {
    "name": "string -- 2-4 word title",
    "description": "string -- 1-2 sentences, Pratchett tone, grounded in evidence"
  },

  "superpowers": [
    {
      "name": "string -- short label",
      "description": "string -- 1 sentence with specific evidence. No flattery, just fact."
    }
  ],

  "communication_style": "string -- 2-3 blunt sentences. How do they talk to AI? Be specific: 'Leads with desired outcome in 1 sentence, adds constraints as bullets' not just 'terse'.",

  "growth_narrative": "string -- 3-5 sentences. Frame through Judgment vs. Reckoning lens. Compare early vs. late sessions. What shifted in how they delegate reckoning vs. retain judgment?",

  "notable_moments": [
    {
      "quote": "string -- exact or near-exact quote from the user",
      "context": "string -- 1 sentence, Pratchett tone"
    }
  ],

  "blind_spots": [
    {
      "name": "string -- short label",
      "description": "string -- 1 sentence, blunt, Pratchett tone. Not 'opportunity' euphemisms -- say what the problem is."
    }
  ],

  "questioning_behavior": {
    "question_ratio": "string -- e.g. '~15% of messages contain questions'",
    "dominant_type": "procedural | conceptual | diagnostic | metacognitive | socratic | strategic",
    "type_examples": [
      {
        "type": "procedural | conceptual | diagnostic | metacognitive | socratic | strategic",
        "quote": "string -- actual quote",
        "bloom_level": "string -- which Bloom's level this maps to"
      }
    ],
    "socratic_usage": "none | occasional | frequent",
    "socratic_example": "string or null -- best example of Socratic questioning, if any",
    "evolution": "string -- how questioning changed over time, if observable"
  },

  "problem_articulation": {
    "level": "vague | basic | structured | diagnostic",
    "weakest_example": "string -- actual quote showing worst articulation",
    "strongest_example": "string -- actual quote showing best articulation",
    "growth": "string -- has articulation improved over time?"
  },

  "domain_expertise": {
    "concepts_demonstrated": ["list of specific concepts the user shows real understanding of -- not just mentions, actual understanding"],
    "depth": "surface | working | deep",
    "growth_evidence": "string -- evidence of growing expertise, or 'insufficient data'",
    "notable_example": "string -- best example of domain knowledge in action"
  },

  "critical_thinking": {
    "ct_level": "strong | acceptable | unacceptable | weak",
    "hypothesis_formation": { "present": true, "example": "string or null" },
    "alternative_consideration": { "present": true, "example": "string or null" },
    "assumption_questioning": { "present": true, "example": "string or null" },
    "evidence_evaluation": { "present": true, "example": "string or null" }
  },

  "vibe_coding_level": {
    "level": 4,
    "name": "Novice | Beginner | Intermediate | Proficient | Advanced | Expert",
    "evidence": "string -- why this level, mapped to specific rubric indicators",
    "strongest_skill": "string -- which sub-skill is strongest",
    "weakest_skill": "string -- which sub-skill needs the most work"
  },

  "vision_and_intent": {
    "orientation": "reactive | tactical | strategic",
    "description": "string -- what is the user's apparent vision/intent?",
    "example": "string -- quote showing strategic or tactical thinking, or null"
  }
}
```

---

## Question Type Reference

When classifying questions in `questioning_behavior.type_examples`:

- **Procedural** -- "how do I install X?", "what's the command for Y?" (Bloom's: Remember/Apply)
- **Conceptual** -- "why does React re-render here?", "what's the difference between X and Y?" (Bloom's: Understand/Analyze)
- **Diagnostic** -- "the error says X, but I think the real issue is Y -- am I right?" (Bloom's: Analyze/Evaluate)
- **Metacognitive** -- "am I approaching this the right way?", "is there a better way to think about this?" (Bloom's: Evaluate)
- **Socratic** -- "what would happen if we removed X?", "can you walk me through why that works?" (Bloom's: Analyze/Evaluate)
- **Strategic** -- "given our constraints, which approach gives us the best tradeoff?" (Bloom's: Evaluate/Create)

## Problem Articulation Levels

When assessing `problem_articulation.level`:

- **Vague** -- "it doesn't work", "something's wrong", "fix this"
- **Basic** -- "I'm getting an error on this page", "the button doesn't do anything"
- **Structured** -- "when I click submit, the form shows a 500 error. I checked the console and see a CORS issue."
- **Diagnostic** -- "the API returns 403 on /auth/refresh when the JWT has expired, but only when the refresh middleware runs before the auth check -- I think the middleware ordering is wrong"

---

## Guidelines

- **Superpowers**: 2-3 max. These must be genuinely distinctive, not generic compliments. "Good at problem solving" is useless. "Runs 5 parallel agents and catches when agent #3 silently diverges from the spec" is useful.
- **Notable moments**: 2-3 quotes that are funny, revealing, or show personality. Use the user's actual words.
- **Blind spots**: 1-2. Be honest. Name the problem directly. Pratchett framing softens the blow without hiding the truth.
- **Growth narrative**: Use Judgment vs. Reckoning as the interpretive frame. If early vs. late sessions show evolution, describe the shift. If data is limited, say so.
- **Questioning behavior**: This is one of the most revealing signals. The quality of someone's questions tells you more about their thinking than the quality of their statements. Include 2-4 examples across different types.
- **Vibe coding level**: Place on the 6-level rubric. Cite the specific indicators that justify the placement. Name strongest and weakest sub-skills.
- **Critical thinking**: Map to the 4-level CT rubric. For each sub-indicator (hypothesis, alternatives, assumptions, evidence), mark present/absent with an example quote.
- **Domain expertise**: Distinguish between mentioning a concept and demonstrating understanding of it.
- **Vision**: Does the user articulate where they want things to go, or just react to what's in front of them?

## What NOT to Do

- Don't produce skills, rules, or actionable config -- that's a separate flow.
- Don't analyze pasted data (JSON blobs, email threads) -- focus on the user's own words.
- Don't invent quotes -- use actual phrases from the conversations, or paraphrase closely.
- Don't be generic or flattering. If the data doesn't support a strong claim, say "insufficient evidence" rather than hedging with filler.
- Don't use marketing language. You are a blunt assessor, not a hype writer.
"""
