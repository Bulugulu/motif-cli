"""Configuration management for Motif CLI."""

from pathlib import Path
import re


def get_motif_dir() -> Path:
    """Get the ~/.motif directory, creating it if needed."""
    motif_dir = Path.home() / ".motif"
    motif_dir.mkdir(parents=True, exist_ok=True)
    return motif_dir


def get_conversations_dir(source: str = "") -> Path:
    """Get the conversations storage directory for a given source."""
    base = get_motif_dir() / "conversations"
    if source:
        d = base / source
    else:
        d = base
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_analysis_dir() -> Path:
    """Get the analysis output directory."""
    d = get_motif_dir() / "analysis"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_cursor_skills_dir() -> Path:
    """Get the global Cursor skills directory."""
    return Path.home() / ".cursor" / "skills"


def get_skill_install_path() -> Path:
    """Get the target path for the motif-analyze skill file."""
    return get_cursor_skills_dir() / "motif-analyze" / "SKILL.md"


# ── Claude Code paths ───────────────────────────────────────────────

def get_claude_code_dir() -> Path:
    """Get the ~/.claude directory (Claude Code's config root)."""
    return Path.home() / ".claude"


def get_claude_code_commands_dir() -> Path:
    """Get the global Claude Code commands directory (~/.claude/commands/)."""
    return get_claude_code_dir() / "commands"


def get_claude_command_install_path() -> Path:
    """Get the target path for the motif slash command in Claude Code."""
    return get_claude_code_commands_dir() / "motif.md"


def get_claude_code_global_config() -> Path:
    """Get Claude Code's global config file (~/.claude/CLAUDE.md)."""
    return get_claude_code_dir() / "CLAUDE.md"


# ── Environment detection ───────────────────────────────────────────

def detect_installed_tools() -> set[str]:
    """Detect which AI coding tools are installed by checking config dirs.

    Returns a set of tool names, e.g. {"cursor", "claude-code"}.
    """
    tools: set[str] = set()
    home = Path.home()

    if (home / ".cursor").is_dir():
        tools.add("cursor")
    if (home / ".claude").is_dir():
        tools.add("claude-code")

    return tools


def strip_skill_frontmatter(content: str) -> str:
    """Strip YAML frontmatter from a SKILL.md, returning plain markdown.

    Claude Code commands are plain markdown — they don't use YAML frontmatter.
    """
    return re.sub(r"^---\n.*?\n---\n*", "", content, count=1, flags=re.DOTALL)
