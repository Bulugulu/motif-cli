"""Rich-based TUI display for the live dashboard."""

from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.columns import Columns

from .metrics import LiveMetrics, get_color, get_color_emoji, THRESHOLDS


def format_tokens(n: float) -> str:
    """Format token count for display: 38200 -> '38.2k'."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(int(n))


def _bar(value: float, max_val: float, width: int = 20) -> str:
    """Create a simple bar chart string."""
    if max_val <= 0:
        return "\u2591" * width
    filled = min(int((value / max_val) * width), width)
    return "\u2588" * filled + "\u2591" * (width - filled)


def _color_wrap(text: str, metric: str, value: float) -> str:
    """Wrap text in Rich color markup based on threshold."""
    color = get_color(metric, value)
    color_map = {"red": "red", "yellow": "yellow", "green": "green", "purple": "magenta"}
    return f"[{color_map[color]}]{text}[/{color_map[color]}]"


def render_full(metrics: LiveMetrics) -> Panel:
    """Render the full TUI dashboard panel.

    Always renders a fixed number of lines so Rich Live can
    overwrite cleanly without duplication artifacts.
    """
    lines = []
    aipm_max = THRESHOLDS["aipm"]["purple"] * 1.5

    # Concurrency
    conc_bar = _bar(metrics.concurrency, 5, 20)
    conc_color = _color_wrap(conc_bar, "concurrency", metrics.concurrency)
    conc_emoji = get_color_emoji("concurrency", metrics.concurrency)
    lines.append(f"  CONCURRENCY  {conc_color}  {metrics.concurrency}       {conc_emoji}")

    # Current AIPM (15s speedometer)
    aipm_bar = _bar(metrics.aipm, aipm_max, 20)
    aipm_color = _color_wrap(aipm_bar, "aipm", metrics.aipm)
    aipm_emoji = get_color_emoji("aipm", metrics.aipm)
    lines.append(f"  AIPM         {aipm_color}  {format_tokens(metrics.aipm)} tok/m {aipm_emoji}")

    # Session average AIPM
    avg_bar = _bar(metrics.session_aipm, aipm_max, 20)
    avg_color = _color_wrap(avg_bar, "aipm", metrics.session_aipm)
    avg_emoji = get_color_emoji("aipm", metrics.session_aipm)
    lines.append(f"  AVG AIPM     {avg_color}  {format_tokens(metrics.session_aipm)} tok/m {avg_emoji}")

    # AIPM per agent — only meaningful with multiple agents
    if metrics.concurrency > 1:
        per_max = THRESHOLDS["aipm_per_agent"]["purple"] * 1.5
        per_bar = _bar(metrics.aipm_per_agent, per_max, 20)
        per_color = _color_wrap(per_bar, "aipm_per_agent", metrics.aipm_per_agent)
        per_emoji = get_color_emoji("aipm_per_agent", metrics.aipm_per_agent)
        lines.append(f"  /AGENT       {per_color}  {format_tokens(metrics.aipm_per_agent)} tok/m {per_emoji}")
    else:
        lines.append("")

    lines.append("")

    # Session stats line
    stats_line = (
        f"  Session: {metrics.session_duration_str}  \u2502  "
        f"Total: {format_tokens(metrics.session_tokens)} tokens  \u2502  "
        f"Prompts: {metrics.session_prompts}"
    )
    lines.append(f"[dim]{stats_line}[/dim]")

    lines.append("")

    # Peaks
    peak_str = f"  Peak AIPM: {format_tokens(metrics.peak_aipm)}"
    if metrics.peak_aipm_ago:
        peak_str += f" ({metrics.peak_aipm_ago})"
    lines.append(peak_str)
    lines.append(f"  Peak Concurrency: {metrics.peak_concurrency}")

    # Status line — always present, content varies
    if metrics.idle_capacity and metrics.concurrency > 0:
        lines.append("  [yellow]Idle capacity \u2014 spin up another agent[/yellow]")
    else:
        lines.append("")

    body = "\n".join(lines)
    return Panel(
        body,
        title="[bold]MOTIF LIVE[/bold]",
        border_style="bright_blue",
        padding=(1, 1),
    )


def render_compact(metrics: LiveMetrics) -> str:
    """Render the single-line compact display."""
    conc_emoji = get_color_emoji("concurrency", metrics.concurrency)
    aipm_emoji = get_color_emoji("aipm", metrics.aipm)

    return (
        f"[bright_blue bold]\u25c8 MOTIF[/bright_blue bold]  "
        f"Conc: {metrics.concurrency} {conc_emoji}  "
        f"AIPM: {format_tokens(metrics.aipm)} {aipm_emoji}  "
        f"Avg: {format_tokens(metrics.session_aipm)}"
    )


def render_summary(metrics: LiveMetrics) -> Panel:
    """Render the session summary card."""
    lines = []

    lines.append(f"  Duration:          {metrics.session_duration_str}")
    lines.append(f"  AI Output:         {format_tokens(metrics.session_tokens)} tokens")
    lines.append(f"  Avg AIPM:          {format_tokens(metrics.session_aipm)}")
    lines.append(f"  Peak AIPM:         {format_tokens(metrics.peak_aipm)}")
    lines.append(f"  Peak Concurrency:  {metrics.peak_concurrency}")
    lines.append(f"  Prompts Sent:      {metrics.session_prompts}")

    if metrics.session_prompts > 0:
        leverage = metrics.session_tokens / metrics.session_prompts
        lines.append(f"  Leverage:          {format_tokens(leverage)} tokens/prompt")

    body = "\n".join(lines)
    return Panel(
        body,
        title="[bold]SESSION COMPLETE[/bold]",
        border_style="bright_blue",
        padding=(1, 1),
    )
