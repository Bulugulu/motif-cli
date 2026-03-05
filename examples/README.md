# Example Output

This directory contains sample Motif output generated from a real developer's Claude Code conversation history (used with permission). The developer builds games using AI as their sole engineering tool — they design features and direct the AI, but don't write code themselves.

**Input:** 386 user messages across 33 sessions (~80K tokens)

**What Motif found:**
- 5 recurring skills (session startup, session wrap-up, bug fix iteration, deploy to production, Unity tool creation)
- 8 rules derived from corrections and preferences
- Communication style profile: terse, delegates fully, decides fast
- 2 improvement areas

## Files

- `analysis.json` — Raw analysis output (what the host agent produces)
- `generated/CLAUDE.md` — Generated project configuration
- `generated/skills/` — Generated skill files
- `report.md` — Summary report (from `motif report`)

**Note:** The Vibe Report (`motif vibe-report`) generates a self-contained HTML file from your own extracted data. Run `motif vibe-report --name "Your Name"` after extracting to see your personalized report with interactive charts.
