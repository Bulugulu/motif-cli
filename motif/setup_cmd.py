"""Setup command: install the motif-analyze skill for Cursor and Claude Code."""

import shutil
from pathlib import Path

from rich.console import Console
from rich.prompt import Confirm

from motif.config import (
    get_skill_install_path,
    get_claude_command_install_path,
    detect_installed_tools,
    strip_skill_frontmatter,
)


def _find_skill_source() -> Path | None:
    """Locate the bundled SKILL.md, trying package root then motif dir."""
    package_root = Path(__file__).resolve().parent.parent
    motif_dir = Path(__file__).resolve().parent
    for candidate in [package_root / "skill" / "SKILL.md", motif_dir / "skill" / "SKILL.md"]:
        if candidate.exists():
            return candidate
    return None


def _install_cursor_skill(skill_src: Path, console: Console, auto: bool) -> bool:
    """Install SKILL.md to ~/.cursor/skills/motif-analyze/SKILL.md."""
    target_path = get_skill_install_path()

    if target_path.exists() and not auto:
        if not Confirm.ask(
            f"Cursor skill already exists at {target_path}. Overwrite?",
            default=True,
            console=console,
        ):
            console.print("[yellow]Skipped Cursor skill.[/yellow]")
            return False

    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(skill_src, target_path)
        console.print(f"[green]{'Updated' if auto else 'Installed'}![/green] Cursor skill at [cyan]{target_path}[/cyan]")
        return True
    except (PermissionError, OSError) as e:
        console.print(f"[red]Error (Cursor):[/red] {e}")
        return False


def _install_claude_command(skill_src: Path, console: Console, auto: bool) -> bool:
    """Install a /motif slash command to ~/.claude/commands/motif.md.

    Converts the SKILL.md to plain markdown (strips YAML frontmatter)
    since Claude Code commands don't use frontmatter.
    """
    target_path = get_claude_command_install_path()

    if target_path.exists() and not auto:
        if not Confirm.ask(
            f"Claude Code command already exists at {target_path}. Overwrite?",
            default=True,
            console=console,
        ):
            console.print("[yellow]Skipped Claude Code command.[/yellow]")
            return False

    try:
        content = skill_src.read_text(encoding="utf-8")
        command_content = strip_skill_frontmatter(content)

        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(command_content, encoding="utf-8")
        console.print(f"[green]{'Updated' if auto else 'Installed'}![/green] Claude Code command at [cyan]{target_path}[/cyan]")
        console.print("  Use [cyan]/motif[/cyan] in Claude Code to trigger it.")
        return True
    except (PermissionError, OSError) as e:
        console.print(f"[red]Error (Claude Code):[/red] {e}")
        return False


def run_setup(console: Console, auto: bool = False) -> bool:
    """Install the motif-analyze skill for detected AI coding tools.

    Installs to:
    - Cursor: ~/.cursor/skills/motif-analyze/SKILL.md (trigger phrases)
    - Claude Code: ~/.claude/commands/motif.md (slash command /motif)

    Detects which tools are installed and only installs for those.
    If auto=True, skips overwrite confirmations (used after upgrades).
    """
    skill_src = _find_skill_source()
    if skill_src is None:
        console.print("[red]Error:[/red] Skill file not found.")
        console.print("Tried: package_root/skill/SKILL.md and motif/skill/SKILL.md")
        return False

    tools = detect_installed_tools()

    if not tools:
        console.print("[yellow]No AI coding tools detected (Cursor or Claude Code).[/yellow]")
        console.print("Install will proceed for both locations anyway.\n")
        tools = {"cursor", "claude-code"}

    any_success = False

    if "cursor" in tools:
        if _install_cursor_skill(skill_src, console, auto):
            any_success = True
    if "claude-code" in tools:
        if _install_claude_command(skill_src, console, auto):
            any_success = True

    if any_success and not auto:
        console.print("\nTrigger phrases: 'vibe report', 'motif live', 'personalize my AI', 'motif analyze'")
        if "claude-code" in tools:
            console.print("In Claude Code, type [cyan]/motif[/cyan] to load the skill.")

    return any_success
