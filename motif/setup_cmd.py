"""Setup command: install the motif-analyze Cursor skill file."""

import shutil
from pathlib import Path

from rich.console import Console
from rich.prompt import Confirm

from motif.config import get_skill_install_path


def run_setup(console: Console, auto: bool = False) -> bool:
    """Install the motif-analyze Cursor skill file.

    Copies skill/SKILL.md to ~/.cursor/skills/motif-analyze/SKILL.md
    Returns True if successful.

    If auto=True, skips the overwrite confirmation (used after upgrades).
    """
    package_root = Path(__file__).resolve().parent.parent
    motif_dir = Path(__file__).resolve().parent
    skill_src = package_root / "skill" / "SKILL.md"
    if not skill_src.exists():
        skill_src = motif_dir / "skill" / "SKILL.md"

    if not skill_src.exists():
        console.print("[red]Error:[/red] Skill file not found.")
        console.print("Tried: package_root/skill/SKILL.md and motif/skill/SKILL.md")
        return False

    target_path = get_skill_install_path()
    target_dir = target_path.parent

    if target_path.exists() and not auto:
        if not Confirm.ask(
            f"Skill already exists at {target_path}. Overwrite?",
            default=True,
            console=console,
        ):
            console.print("[yellow]Skipped.[/yellow]")
            return False

    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(skill_src, target_path)
        console.print(f"[green]{'Updated' if auto else 'Installed'}![/green] motif-analyze skill at [cyan]{target_path}[/cyan]")
        if not auto:
            console.print("Trigger phrases: 'vibe report', 'motif live', 'personalize my AI', 'motif analyze'")
        return True
    except PermissionError:
        console.print(f"[red]Error:[/red] Permission denied writing to {target_path}")
        return False
    except OSError as e:
        console.print(f"[red]Error:[/red] {e}")
        return False
