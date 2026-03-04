"""Configuration management for Motif CLI."""

from pathlib import Path
import json
import platform


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
    system = platform.system()
    home = Path.home()

    if system == "Windows":
        return home / ".cursor" / "skills"
    elif system == "Darwin":
        return home / ".cursor" / "skills"
    else:
        return home / ".cursor" / "skills"


def get_skill_install_path() -> Path:
    """Get the target path for the motif-analyze skill file."""
    return get_cursor_skills_dir() / "motif-analyze" / "SKILL.md"
