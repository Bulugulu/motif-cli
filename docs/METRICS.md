# Vibe Report Metrics

Documentation for every metric in Motif's Vibe Report. Understanding what's measured and how.

## Hero Stats

These headline numbers appear at the top of the report.

### Total Sessions
Number of distinct AI coding sessions detected. A session is a single conversation thread (one Cursor composer tab or one Claude Code session).

### Projects
Number of distinct projects you worked on (detected from file paths in your conversations).

### Autonomy Ratio
**Formula:** `(assistant_messages + total_tool_calls) / user_messages`

Measures how many discrete agent actions happen per human prompt. The floor is 1.0x (one response per prompt). Everything above comes from tool calls — file reads, edits, shell commands, searches, lint checks, etc.

**What counts as an agent action:**
- Each assistant response (1 per user message)
- Each tool call within a response (file read, file write, shell command, grep, etc.)

**What does NOT count:**
- Thinking/reasoning tokens (explicitly excluded)
- Tool results (environment input, not agent output)

**Interpretation:** Higher = more effective delegation. A prompt like "refactor this across the codebase" might yield 20+ tool calls, giving a high ratio. A prompt like "explain this function" yields 1 response with no tool calls, giving 1.0x.

### Output Density
**Formula:** `total_agent_output_chars / user_messages`

Measures the volume of agent-authored content per human prompt. Unlike autonomy ratio (which counts discrete actions), this captures the *substance* of each action.

**What counts as agent output:**
- Response text (the prose/explanation the agent writes)
- Tool call arguments (the code, file paths, and commands the agent authors)

**What does NOT count:**
- Thinking/reasoning blocks
- Tool results (file contents returned from reads, grep output, etc.)

**Interpretation:** Higher = more substantial work per prompt. Writing a 500-line component produces more output chars than reading a file, even though both are 1 tool call. Together with autonomy ratio, this gives a two-dimensional view: autonomy = breadth of actions, output density = volume per action.

### Peak Concurrency
The maximum number of AI sessions you had running simultaneously. Based on overlapping session start/end times.

**Why it matters:** METR's transcript analysis found that developers averaging 2.3+ concurrent sessions achieved ~12x time savings, while those running ~1 session averaged ~2x.

## Charts

### Agent Concurrency (over time)
Weekly average peak concurrent sessions. Shows how your ability to manage multiple agents has evolved.

### Autonomy Ratio (over time)
Weekly autonomy ratio. Calculated the same as the hero stat but broken down by week to show trends.

### Output Density (over time)
Weekly output density. Agent-authored characters per user message, broken down by week.

### Project Constellation
Visual galaxy where each "star" represents a project, sized by message count.

## Growth Scorecard

Compares your first 25% of sessions to your most recent 25% across five dimensions:

### Specification Depth
Average prompt length (characters). Longer prompts suggest more detailed specifications, giving the agent more context for better first-try results.

### Autonomy Ratio
Same formula as the hero stat, but comparing early vs. recent sessions.

### Session Depth
Average messages per session. More messages per session often means tackling bigger, more complex tasks.

### Tool Density
Average tool calls per session. More tool calls means the agent is doing more discrete work for you per session.

### Output Density
Average agent-authored characters per user message, comparing early vs. recent sessions.

## Personality Stats

### Swear Count
Total profanity detected in your messages. Classified as: Saint (≤10), Mostly Composed (≤50), Has Opinions (≤200), Passionate Debugger (>200).

### Peak Session Swears
Most swears in a single session — your peak frustration moment.

### Frustration Phrases
Common frustration expressions like "still broken", "try again", "just fix it", ranked by frequency.

### Catchphrases
Your signature phrases like "commit and push", "ship it", "let's go", ranked by frequency.

### Clean Streak
Longest consecutive run of sessions without any swearing.

### Novels Equivalent
Total characters typed to AI, converted to novel equivalents (~500,000 chars/novel).

### Longest Session
Most messages in a single session — your marathon coding session.

### Busiest Day
The calendar day with the most messages.
