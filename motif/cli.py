"""Motif CLI — discover your coding patterns from AI conversations."""

import click
from rich.console import Console
from rich.table import Table

import motif

console = Console()


@click.group()
@click.version_option(version=motif.__version__, prog_name="motif")
@click.pass_context
def cli(ctx):
    """Motif — discover your coding patterns from AI conversations.

    Analyze your Cursor and Claude Code conversations to generate
    personalized .cursorrules, CLAUDE.md, and skills files.
    """
    ctx.ensure_object(dict)
    if ctx.invoked_subcommand != "update":
        from motif.update import print_update_notice
        print_update_notice(console)


# ── Extract ─────────────────────────────────────────────────────────

@cli.group()
def extract():
    """Extract conversations from AI coding tools."""
    pass


@extract.command("cursor")
def extract_cursor():
    """Extract conversations from Cursor's state database."""
    from motif.extractors.cursor import extract_conversations, get_cursor_db_path, group_by_project
    from motif.store import save_conversations

    db_path = get_cursor_db_path()
    console.print(f"Reading from: [cyan]{db_path}[/cyan]")

    if not db_path.exists():
        console.print("[red]Cursor database not found.[/red]")
        console.print("Expected locations:")
        console.print("  Windows: %APPDATA%\\Cursor\\User\\globalStorage\\state.vscdb")
        console.print("  macOS:   ~/Library/Application Support/Cursor/User/globalStorage/state.vscdb")
        console.print("  Linux:   ~/.config/Cursor/User/globalStorage/state.vscdb")
        raise SystemExit(1)

    console.print("Extracting conversations...")
    messages = extract_conversations(str(db_path))

    if not messages:
        console.print("[yellow]No conversations found.[/yellow]")
        return

    projects = group_by_project(messages)
    saved = save_conversations(messages, "cursor")

    console.print(f"\n[green]Extracted {len(messages)} messages across {len(projects)} projects:[/green]")
    for name, msgs in sorted(projects.items(), key=lambda x: -len(x[1])):
        user_count = sum(1 for m in msgs if m["role"] == "user")
        console.print(f"  {name}: {len(msgs)} messages ({user_count} user)")

    if saved:
        first_path = next(iter(saved.values()))
        console.print(f"\nSaved to: [cyan]{first_path.parent}[/cyan]")


@extract.command("claude")
def extract_claude():
    """Extract conversations from Claude Code session files."""
    from motif.extractors.claude_code import extract_conversations, get_claude_data_path, group_by_project
    from motif.store import save_conversations

    claude_path = get_claude_data_path()
    console.print(f"Reading from: [cyan]{claude_path}[/cyan]")

    if not claude_path.exists():
        console.print("[yellow]Claude Code data directory not found.[/yellow]")
        console.print("No Claude Code conversations to extract.")
        return

    console.print("Extracting conversations...")
    messages = extract_conversations(str(claude_path))

    if not messages:
        console.print("[yellow]No conversations found.[/yellow]")
        return

    projects = group_by_project(messages)
    saved = save_conversations(messages, "claude-code")

    console.print(f"\n[green]Extracted {len(messages)} messages across {len(projects)} projects:[/green]")
    for name, msgs in sorted(projects.items(), key=lambda x: -len(x[1])):
        user_count = sum(1 for m in msgs if m["role"] == "user")
        console.print(f"  {name}: {len(msgs)} messages ({user_count} user)")

    if saved:
        first_path = next(iter(saved.values()))
        console.print(f"\nSaved to: [cyan]{first_path.parent}[/cyan]")


@extract.command("all")
@click.pass_context
def extract_all(ctx):
    """Extract from all available sources (Cursor + Claude Code)."""
    console.print("[bold]Extracting from all sources...[/bold]\n")

    console.rule("Cursor")
    try:
        ctx.invoke(extract_cursor)
    except SystemExit:
        console.print("[yellow]Skipping Cursor (not available).[/yellow]")

    console.print()
    console.rule("Claude Code")
    try:
        ctx.invoke(extract_claude)
    except SystemExit:
        console.print("[yellow]Skipping Claude Code (not available).[/yellow]")

    console.print("\n[green]Extraction complete.[/green]")


# ── List ────────────────────────────────────────────────────────────

@cli.command("list")
def list_projects():
    """Show all extracted projects with message counts."""
    from motif.store import list_projects as _list_projects

    projects = _list_projects()

    if not projects:
        console.print("[yellow]No extracted data found. Run 'motif extract all' first.[/yellow]")
        return

    table = Table(title="Extracted Projects")
    table.add_column("Project", style="cyan")
    table.add_column("Source", style="magenta")
    table.add_column("Messages", justify="right")
    table.add_column("User Msgs", justify="right")
    table.add_column("Date Range")

    total_messages = 0
    for p in projects:
        table.add_row(
            p["project"],
            p["source"],
            str(p["message_count"]),
            str(p["user_count"]),
            p["date_range"],
        )
        total_messages += p["message_count"]

    console.print(table)
    console.print(f"\n[bold]{total_messages}[/bold] messages across [bold]{len(projects)}[/bold] projects")

    # Show merge suggestions for projects with the same normalized name
    merge_groups = {}
    for p in projects:
        if p.get("merge_group"):
            norm = p["normalized_name"]
            if norm not in merge_groups:
                merge_groups[norm] = set()
            merge_groups[norm].update(p["merge_group"])

    if merge_groups:
        console.print(f"\n[yellow]Possible duplicates (same project, different names):[/yellow]")
        for norm, names in merge_groups.items():
            names_str = ", ".join(f"[cyan]{n}[/cyan]" for n in sorted(names))
            console.print(f"  {names_str}  ->  normalized: [bold]{norm}[/bold]")
        console.print(f"\n[dim]These will be auto-merged during 'motif analyze --prepare'.[/dim]")


# ── Analyze ─────────────────────────────────────────────────────────

def _resolve_project(project_arg, console):
    """Auto-detect project name if not explicitly provided.

    Returns the resolved project name or raises SystemExit.
    """
    from motif.store import list_projects as _list_projects
    from motif.analysis.pipeline import normalize_project_name

    if project_arg is not None:
        return project_arg

    import os
    cwd_name = os.path.basename(os.getcwd()).lower().strip()
    projects = _list_projects()
    known_projects = {p["project"].lower() for p in projects}
    known_normalized = {normalize_project_name(p["project"].lower()): p["project"] for p in projects}

    if cwd_name and cwd_name in known_projects:
        console.print(f"Auto-detected project from cwd: [cyan]{cwd_name}[/cyan]")
        return cwd_name

    # Try normalized match (e.g., cwd "journey-map-makers" matches "c-dev-journey-map-makers")
    cwd_normalized = normalize_project_name(cwd_name)
    if cwd_normalized in known_normalized:
        matched = known_normalized[cwd_normalized]
        console.print(f"Auto-detected project from cwd: [cyan]{cwd_name}[/cyan] (matched '{matched}')")
        return cwd_name

    if projects:
        project = projects[0]["project"]
        console.print(f"Project '{cwd_name}' not found in extracted data.")
        console.print(f"Falling back to: [cyan]{project}[/cyan] (most messages)")
        console.print(f"Tip: run 'motif extract all' from the {cwd_name} workspace first, or use --project NAME")
        return project

    console.print("[red]No projects found.[/red]")
    raise SystemExit(1)


@cli.command()
@click.option("--prepare", is_flag=True, required=True, help="Prepare analysis data + prompt for the host agent")
@click.option("--project", "-p", default=None, help="Project to analyze (default: current directory name)")
@click.option("--budget", "-b", default=None, type=int, help="Token budget (default: 200000 for vibe-report, 60000 for full)")
@click.option("--mode", "-m", default="full", type=click.Choice(["full", "vibe-report"]), help="Analysis mode: 'full' for Personalize AI, 'vibe-report' for qualitative vibe report")
@click.option("--stats", is_flag=True, help="Show pipeline stats only, don't write output")
@click.option("--no-filter", is_flag=True, help="Skip relevance filtering (include all project-scoped conversations)")
@click.option("--preview", is_flag=True, help="Show session relevance scores without running full analysis")
def analyze(prepare, project, budget, mode, stats, no_filter, preview):
    """Analyze extracted conversations for patterns.

    Usage: motif analyze --prepare [--project NAME] [--budget N] [--mode MODE]

    Modes:
      full         Full Personalize AI analysis (skills, rules, style). Default.
      vibe-report  Qualitative analysis for the shareable vibe report.
                   Strips system noise, puts instructions first.

    The pipeline filters misattributed conversations by checking whether
    file paths in each session match the target project. Use --no-filter
    to disable this, or --preview to inspect scores before running.
    """
    from motif.store import load_all_conversations
    from motif.analysis.pipeline import (
        prepare_analysis, scope_to_project, preview_relevance,
    )
    from motif.config import get_analysis_dir

    all_messages = load_all_conversations()

    if not all_messages:
        console.print("[red]No extracted data found. Run 'motif extract all' first.[/red]")
        raise SystemExit(1)

    project = _resolve_project(project, console)

    # Preview mode: show relevance scores and exit
    if preview:
        scoped = scope_to_project(all_messages, project)
        if not scoped:
            console.print(f"[yellow]No messages found for project '{project}'.[/yellow]")
            return

        scores = preview_relevance(scoped, project)

        # Show removed sessions first (the ones the user cares about inspecting)
        removed_sessions = [s for s in scores if not s["keep"]]
        kept_sessions = [s for s in scores if s["keep"]]
        removed_count = len(removed_sessions)
        removed_msgs = sum(s["total_messages"] for s in removed_sessions)

        if removed_sessions:
            console.print(f"\n[bold red]Sessions to REMOVE ({removed_count}):[/bold red]")
            shown = sorted(removed_sessions, key=lambda x: -(x["total_messages"]))
            limit = 25
            for s in shown[:limit]:
                short_id = s["session_id"].split(":")[-1][:12] if ":" in s["session_id"] else s["session_id"][:12]
                date = s.get("timestamp") or "?"
                sample = (s.get("sample") or "")[:70].replace("\n", " ")
                console.print(
                    f"  [cyan]{short_id}[/cyan] ({date}, {s['total_messages']} msgs, "
                    f"{s['paths_total']} paths) [dim]{sample}[/dim]"
                )
            if len(shown) > limit:
                console.print(f"  [dim]... and {len(shown) - limit} more[/dim]")
        else:
            console.print("[green]No sessions would be removed.[/green]")

        no_paths = sum(1 for s in kept_sessions if s["reason"] == "no_paths_detected")
        with_paths = len(kept_sessions) - no_paths

        console.print(f"\n[bold]{len(scores)}[/bold] sessions total:")
        console.print(f"  [green]{len(kept_sessions)}[/green] kept ({with_paths} with matching paths, {no_paths} with no file paths)")
        console.print(f"  [red]{removed_count}[/red] would be removed ({removed_msgs} messages) -- file paths outside project")
        if removed_count:
            console.print(f"\nUse [cyan]--no-filter[/cyan] to keep all sessions.")
        return

    from motif.analysis.pipeline import BUDGET_VIBE_REPORT, BUDGET_DEFAULT
    effective_budget = budget if budget is not None else (
        BUDGET_VIBE_REPORT if mode == "vibe-report" else BUDGET_DEFAULT
    )
    mode_label = "vibe report" if mode == "vibe-report" else "full"
    console.print(f"Preparing analysis for [bold]{project}[/bold] (mode: {mode_label}, budget: {effective_budget} tokens)...")

    output, pipeline_stats = prepare_analysis(
        all_messages, project, budget,
        skip_relevance_filter=no_filter,
        mode=mode,
    )

    # Show stats
    console.print(f"\n[bold]Pipeline stats:[/bold]")
    console.print(f"  Raw messages (all projects): {pipeline_stats['raw_count']}")
    console.print(f"  Scoped to '{project}': {pipeline_stats['scoped_count']}")

    rel_removed = pipeline_stats.get("relevance_sessions_removed", 0)
    rel_msgs = pipeline_stats.get("relevance_messages_removed", 0)
    if rel_removed > 0:
        console.print(f"  [yellow]Relevance filter: removed {rel_removed} sessions ({rel_msgs} messages) — file paths outside project[/yellow]")
    elif no_filter:
        console.print(f"  Relevance filter: [dim]skipped (--no-filter)[/dim]")
    else:
        no_paths = pipeline_stats.get("relevance_sessions_no_paths", 0)
        console.print(f"  Relevance filter: all sessions passed ({no_paths} had no file paths)")
    console.print(f"  After relevance filter: {pipeline_stats['relevance_count']}")

    console.print(f"  After noise filter: {pipeline_stats['filtered_count']} (dropped {pipeline_stats['dropped_noise']})")
    if pipeline_stats.get("system_noise_stripped_tokens"):
        console.print(f"  System noise stripped: ~{pipeline_stats['system_noise_stripped_tokens']} tokens")
    console.print(f"  Final messages: {pipeline_stats['final_count']}")
    console.print(f"  Estimated tokens: {pipeline_stats['estimated_tokens']}")
    if pipeline_stats.get("budget_applied"):
        console.print(f"  [yellow]Budget reduction applied[/yellow]")

    user_count = pipeline_stats["scoped_count"] // 2  # rough estimate
    if user_count < 20:
        console.print(f"\n[yellow]Note: Limited data ({user_count} est. user messages). Findings may be thin.[/yellow]")

    if rel_removed > 0:
        console.print(f"\n[dim]Tip: use --preview to inspect removed sessions, or --no-filter to include them.[/dim]")

    if stats:
        return

    # Write output
    out_dir = get_analysis_dir()
    safe_project = "".join(c if c.isalnum() or c in "-_" else "_" for c in project)
    from datetime import datetime
    timestamp = datetime.now().strftime('%Y-%m-%d-%H%M')

    if mode == "vibe-report" and isinstance(output, list):
        written_paths = []
        for suffix, content in output:
            out_path = out_dir / f"prepared-{safe_project}-{timestamp}-{suffix}.md"
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(content)
            written_paths.append(out_path)

        batch_count = sum(1 for s, _ in output if s.startswith("batch-"))
        console.print(f"\n[green]Prepared analysis written to {len(written_paths)} files:[/green]")
        for p in written_paths:
            if "instructions" in p.name:
                label = "[bold cyan]>>[/bold cyan]"
            elif "analysis-brief" in p.name:
                label = "[bold cyan]>>[/bold cyan]"
            else:
                label = "  "
            console.print(f"  {label} [cyan]{p}[/cyan]")
        console.print(f"\nData is split across {batch_count} batch file(s), ~20k tokens each.")
        console.print("Your agent should read the instructions file first, then the batch files.")
        console.print("The analysis-brief file is a compact version for delegating to subagents.")
    else:
        out_path = out_dir / f"prepared-{safe_project}-{timestamp}.md"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(output)

        console.print(f"\n[green]Prepared analysis written to:[/green]")
        console.print(f"  [cyan]{out_path}[/cyan]")
        console.print(f"\nThe file contains {pipeline_stats['final_count']} messages + analysis instructions.")
        console.print("Your Cursor agent can read this file and follow the analysis instructions.")


# ── Status ──────────────────────────────────────────────────────────

@cli.command()
@click.option("--project", "-p", default=None, help="Project to check status for (default: current directory name)")
def status(project):
    """Show status of existing Motif artifacts for a project."""
    import json
    from datetime import datetime
    from pathlib import Path

    from motif.config import get_motif_dir, get_analysis_dir, get_conversations_dir
    from motif.analysis.pipeline import normalize_project_name

    project = _resolve_project(project, console)
    safe_project = "".join(c if c.isalnum() or c in "-_" else "_" for c in project)
    project_normalized = normalize_project_name(project.lower())

    # 1. Last extraction date — conversations matching project
    conv_dir = get_conversations_dir()
    extracted_info = None
    for json_path in conv_dir.rglob("*.json"):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            file_project = data.get("project", "")
            if normalize_project_name(file_project.lower()) == project_normalized:
                extracted_at = data.get("extracted_at")
                msg_count = data.get("message_count", 0)
                if extracted_at:
                    dt = datetime.fromisoformat(extracted_at.replace("Z", "+00:00"))
                    if extracted_info is None or dt > extracted_info[0]:
                        extracted_info = (dt, msg_count)
        except (json.JSONDecodeError, OSError):
            continue

    # 2. Last analysis prepared — prepared-{safe_project}-*.md
    analysis_dir = get_analysis_dir()
    prepared_matches = sorted(analysis_dir.glob(f"prepared-{safe_project}-*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    prepared_info = None
    if prepared_matches:
        p = prepared_matches[0]
        prepared_info = (datetime.fromtimestamp(p.stat().st_mtime), p)

    # 3. Last analysis JSON — analysis-{safe_project}-*.json
    analysis_json_matches = sorted(analysis_dir.glob(f"analysis-{safe_project}-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    analysis_json_info = None
    if analysis_json_matches:
        p = analysis_json_matches[0]
        analysis_json_info = (datetime.fromtimestamp(p.stat().st_mtime), p)

    # 4–6. Generated dir: last mtime, skill count, CLAUDE.md
    gen_dir = get_motif_dir() / "generated"
    skills_dir = gen_dir / "skills"
    gen_mtime = None
    skill_count = 0
    claude_exists = (gen_dir / "CLAUDE.md").exists()
    if gen_dir.exists():
        for f in gen_dir.rglob("*"):
            if f.is_file():
                mtime = datetime.fromtimestamp(f.stat().st_mtime)
                if gen_mtime is None or mtime > gen_mtime:
                    gen_mtime = mtime
        if skills_dir.exists():
            skill_count = sum(1 for f in skills_dir.rglob("*") if f.is_file())

    # Check if any artifacts exist
    has_any = extracted_info or prepared_info or analysis_json_info or (gen_mtime is not None)

    if not has_any:
        console.print(f"Motif status for: [bold]{project}[/bold]\n")
        console.print("  [dim]No artifacts found.[/dim] Run [cyan]motif analyze --prepare --project " + project + "[/cyan] to get started.")
        return

    def _fmt_date(dt):
        return dt.strftime("%b %d, %Y %I:%M %p") if hasattr(dt, "strftime") else str(dt)

    console.print(f"Motif status for: [bold]{project}[/bold]\n")

    if extracted_info:
        dt, count = extracted_info
        console.print(f"  [bold]Extracted:[/bold]     {_fmt_date(dt)}  ({count} messages)")
    else:
        console.print("  [bold]Extracted:[/bold]     [dim]not found[/dim]")

    if prepared_info:
        dt, path = prepared_info
        path_str = str(path).replace(str(Path.home()), "~")
        console.print(f"  [bold]Analysis:[/bold]      {_fmt_date(dt)}  [dim]{path_str}[/dim]")
    else:
        console.print("  [bold]Analysis:[/bold]      [dim]not found[/dim]")

    if analysis_json_info:
        dt, path = analysis_json_info
        path_str = str(path).replace(str(Path.home()), "~")
        console.print(f"  [bold]Analysis JSON:[/bold]  {_fmt_date(dt)}  [dim]{path_str}[/dim]")
    else:
        console.print("  [bold]Analysis JSON:[/bold]  [dim]not found[/dim]")

    if gen_mtime is not None:
        parts = []
        if skill_count:
            parts.append(f"{skill_count} skills")
        if claude_exists:
            parts.append("CLAUDE.md")
        suffix = f"  ({', '.join(parts)})" if parts else ""
        console.print(f"  [bold]Generated:[/bold]    {_fmt_date(gen_mtime)}{suffix}")
    else:
        console.print("  [bold]Generated:[/bold]    [dim]not found[/dim]")

    if not analysis_json_info and (extracted_info or prepared_info):
        console.print("\n  [yellow]No analysis JSON found.[/yellow] Run a full analysis to enable quick regeneration of skills/rules.")


# ── Rules ───────────────────────────────────────────────────────────

@cli.command()
@click.argument("analysis_file", type=click.Path(exists=True))
@click.option("--dry-run", is_flag=True, help="Preview what would be generated without writing files")
@click.option("--apply", is_flag=True, help="Deploy skill files to project/user directories")
@click.option("--project", "-p", default=None, help="Project name for CLAUDE.md header")
def rules(analysis_file, dry_run, apply, project):
    """Generate config files (CLAUDE.md, skills) from analysis JSON.

    ANALYSIS_FILE is the JSON output from your agent's analysis.

    Motif never writes to your CLAUDE.md directly. The generated CLAUDE.md
    is saved to ~/.motif/generated/ as a reference — your agent should read
    it and merge the relevant sections into your existing CLAUDE.md.
    """
    from motif.rules.generator import load_analysis, generate_all, preview_generation, deploy_files
    from motif.config import get_motif_dir
    import json

    try:
        analysis = load_analysis(analysis_file)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        console.print(f"[red]Error loading analysis:[/red] {e}")
        raise SystemExit(1)

    project_name = project or _detect_project_name(analysis)

    if dry_run:
        console.print(preview_generation(analysis))
        return

    out_dir = get_motif_dir() / "generated"
    out_dir.mkdir(parents=True, exist_ok=True)

    generated = generate_all(analysis, out_dir, project_name)

    for rel_path, content in generated.items():
        dest = out_dir / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")

    console.print(f"[green]Generated {len(generated)} files to:[/green] [cyan]{out_dir}[/cyan]")
    for rel_path in sorted(generated):
        console.print(f"  {rel_path}")

    claude_path = out_dir / "CLAUDE.md"
    if claude_path.exists():
        console.print(f"\n[bold]CLAUDE.md reference:[/bold] [cyan]{claude_path}[/cyan]")
        console.print(f"[dim]Motif does not edit your CLAUDE.md. Read the reference above and merge the rules you want.[/dim]")

    if apply:
        deployed = deploy_files(generated, out_dir)
        if deployed:
            console.print(f"\n[green]Deployed {len(deployed)} skill files:[/green]")
            for d in deployed:
                console.print(f"  [cyan]{d}[/cyan]")
        else:
            console.print(f"\n[dim]No skill files to deploy.[/dim]")
    else:
        skill_count = sum(1 for r in generated if r != "CLAUDE.md")
        if skill_count:
            console.print(f"\nRun [cyan]motif rules {analysis_file} --apply[/cyan] to deploy {skill_count} skill files.")


def _detect_project_name(analysis: dict) -> str:
    """Infer project name from analysis context or cwd."""
    ctx = analysis.get("project_context") or {}
    desc = ctx.get("description", "")
    if desc:
        return desc.split(".")[0].strip()[:60]
    import os
    return os.path.basename(os.getcwd())


# ── Report ──────────────────────────────────────────────────────────

@cli.command()
@click.argument("analysis_file", type=click.Path(exists=True))
@click.option("--output", "-o", default=None, help="Output file path (default: ~/.motif/reports/report-{date}.md)")
@click.option("--project", "-p", default=None, help="Project name for report header")
def report(analysis_file, output, project):
    """Generate a summary report from analysis JSON.

    ANALYSIS_FILE is the JSON output from your agent's analysis.
    """
    from motif.rules.generator import load_analysis
    from motif.report.markdown import generate_report
    from motif.config import get_motif_dir
    from datetime import datetime
    import json

    try:
        analysis = load_analysis(analysis_file)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        console.print(f"[red]Error loading analysis:[/red] {e}")
        raise SystemExit(1)

    project_name = project or _detect_project_name(analysis)
    report_md = generate_report(analysis, project_name)

    if output:
        from pathlib import Path
        out_path = Path(output)
    else:
        reports_dir = get_motif_dir() / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        out_path = reports_dir / f"report-{datetime.now().strftime('%Y-%m-%d')}.md"

    out_path.write_text(report_md, encoding="utf-8")
    console.print(f"[green]Report written to:[/green] [cyan]{out_path}[/cyan]")


# ── Vibe Report ─────────────────────────────────────────────────────

@cli.command("vibe-report")
@click.option("--output", "-o", default=None, help="Output file path (default: ~/.motif/reports/vibe-report-{date}.html)")
@click.option("--analysis", "-a", default=None, type=click.Path(exists=True), help="Analysis JSON for archetype generation")
@click.option("--name", "-n", default=None, help="Your name for the report header")
@click.option("--open/--no-open", "open_report", default=True, help="Auto-open report in browser (default: True)")
def vibe_report(output, analysis, name, open_report):
    """Generate a shareable HTML vibe report from all extracted conversations.

    Computes metrics across all your projects and produces a visual,
    self-contained HTML page — your "Spotify Wrapped" for vibe coding.
    """
    from motif.store import load_all_conversations
    from motif.report.metrics import compute_all_metrics
    from motif.report.html import generate_html_report
    from motif.config import get_motif_dir
    from datetime import datetime
    import webbrowser

    console.print("[bold]Generating your Vibe Report...[/bold]\n")

    all_messages = load_all_conversations()
    if not all_messages:
        console.print("[red]No extracted data found. Run 'motif extract all' first.[/red]")
        raise SystemExit(1)

    console.print(f"  Loaded {len(all_messages)} messages")

    console.print("  Computing metrics...")
    metrics = compute_all_metrics(all_messages)

    hero = metrics["hero"]
    conc = metrics["concurrency"]
    console.print(f"  [dim]Sessions: {hero['total_sessions']} | Projects: {hero['total_projects']} | Autonomy: {hero['autonomy_ratio']}x[/dim]")
    console.print(f"  [dim]Peak concurrency: {conc['peak_concurrent']} sessions | Avg daily: {conc['avg_daily_peak']:.1f}[/dim]")

    analysis_data = None
    if analysis:
        import json
        try:
            with open(analysis, "r", encoding="utf-8") as f:
                analysis_data = json.load(f)
            archetype = (analysis_data or {}).get("archetype")
            if archetype:
                console.print(f"  [dim]Archetype: {archetype.get('name', '?')}[/dim]")
            superpowers = (analysis_data or {}).get("superpowers") or []
            if superpowers:
                console.print(f"  [dim]Superpowers: {len(superpowers)} identified[/dim]")
        except (json.JSONDecodeError, OSError) as e:
            console.print(f"  [yellow]Warning: could not load analysis file: {e}[/yellow]")

    user_name = name or "Vibe Coder"
    console.print("  Generating HTML...")
    html = generate_html_report(metrics, analysis=analysis_data, user_name=user_name)

    if output:
        from pathlib import Path
        out_path = Path(output)
    else:
        reports_dir = get_motif_dir() / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        out_path = reports_dir / f"vibe-report-{datetime.now().strftime('%Y-%m-%d-%H%M')}.html"

    out_path.write_text(html, encoding="utf-8")
    console.print(f"\n[green]Vibe Report written to:[/green] [cyan]{out_path}[/cyan]")

    if open_report:
        webbrowser.open(out_path.resolve().as_uri())
        console.print("Opened in your browser!")
    else:
        console.print("Open in a browser to see your report!")


# ── Live Dashboard ──────────────────────────────────────────────────

@cli.command()
@click.option("--compact", is_flag=True, help="Single-line compact display mode")
@click.option("--interval", "-i", default=2.0, type=float, help="Poll interval in seconds (default: 2)")
@click.option("--history", is_flag=True, help="Include existing session data (default: only new activity)")
@click.option("--summary", is_flag=True, help="Show summary of current session data and exit")
@click.option("--idle-timeout", default=300, type=int, help="Auto-end session after N seconds of inactivity (0 to disable)")
def live(compact, interval, history, summary, idle_timeout):
    """Real-time AI productivity dashboard.

    Shows AIPM (AI tokens per minute), concurrency, and per-agent
    efficiency as a live-updating TUI. Like StarCraft APM, but for
    vibe coding.

    \b
    Metrics:
      Concurrency   Agents actively generating tokens right now
      AIPM          Current AI output tokens/min (15s window)
      Avg AIPM      Session average AI output tokens/min
      /Agent        Current tokens/min per active agent
    """
    from motif.live.runner import run_live

    if summary:
        from motif.live.poller import ClaudeCodePoller
        from motif.live.metrics import MetricsEngine
        from motif.live.display import render_summary

        poller = ClaudeCodePoller()
        engine = MetricsEngine()
        messages = poller.poll()
        engine.ingest(messages)
        metrics = engine.compute()

        if metrics.total_tokens > 0:
            console.print(render_summary(metrics))
        else:
            console.print("[dim]No AI activity found.[/dim]")
        return

    run_live(
        compact=compact,
        poll_interval=interval,
        include_history=history,
        idle_timeout=idle_timeout,
    )


# ── Setup ───────────────────────────────────────────────────────────

@cli.command()
def setup():
    """Install the motif-analyze skill for Cursor and/or Claude Code."""
    from motif.setup_cmd import run_setup
    run_setup(console)


# ── Update ──────────────────────────────────────────────────────────

@cli.command()
def update():
    """Check for updates and upgrade motif-cli if a newer version is available."""
    from motif.update import check_for_update, run_upgrade

    console.print("Checking for updates...")
    result = check_for_update(force=True)

    if result is None:
        console.print("[yellow]Could not reach PyPI. Check your internet connection.[/yellow]")
        return

    if not result["update_available"]:
        console.print(f"[green]You're on the latest version ({result['current']}).[/green]")
        return

    console.print(
        f"[yellow]Update available:[/yellow] {result['current']} -> [bold]{result['latest']}[/bold]\n"
    )

    if click.confirm("Upgrade now?", default=True):
        console.print(f"Running: pip install --upgrade motif-cli\n")
        success = run_upgrade()
        if success:
            console.print(f"\n[green]Upgraded to {result['latest']}![/green]")
            from motif.setup_cmd import run_setup
            from motif.config import get_skill_install_path, get_claude_command_install_path
            if get_skill_install_path().exists() or get_claude_command_install_path().exists():
                console.print("Updating installed skills...")
                run_setup(console, auto=True)
        else:
            console.print("\n[red]Upgrade failed.[/red] Try manually: pip install --upgrade motif-cli")
    else:
        console.print("Skipped. Run [cyan]pip install --upgrade motif-cli[/cyan] anytime.")


# ── Entry point ─────────────────────────────────────────────────────

if __name__ == "__main__":
    cli()
