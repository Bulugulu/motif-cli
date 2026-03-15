"""Main loop for the live dashboard."""

import json
import time
import signal
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console
from rich.live import Live

from .poller import ClaudeCodePoller
from .metrics import MetricsEngine, LiveMetrics
from .display import render_full, render_compact, render_summary


def _get_sessions_dir() -> Path:
    d = Path.home() / ".motif" / "sessions"
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_session(metrics: LiveMetrics):
    """Persist session metrics to ~/.motif/sessions/ as JSON."""
    sessions_dir = _get_sessions_dir()
    now = datetime.now(timezone.utc)
    filename = f"session-{now.strftime('%Y-%m-%d-%H%M%S')}.json"

    record = {
        "timestamp": now.isoformat(),
        "session_start": datetime.fromtimestamp(metrics.session_start, tz=timezone.utc).isoformat(),
        "duration": metrics.session_duration_str,
        "session_tokens": metrics.session_tokens,
        "session_prompts": metrics.session_prompts,
        "session_aipm": round(metrics.session_aipm, 1),
        "peak_aipm": round(metrics.peak_aipm, 1),
        "avg_concurrency": round(metrics.avg_concurrency, 2),
        "peak_concurrency": metrics.peak_concurrency,
        "leverage": round(metrics.session_tokens / metrics.session_prompts, 1) if metrics.session_prompts > 0 else 0,
    }

    path = sessions_dir / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)

    # Also update records.json with personal bests
    _update_records(metrics, sessions_dir)


def _update_records(metrics: LiveMetrics, sessions_dir: Path):
    """Update personal best records."""
    records_path = sessions_dir / "records.json"
    try:
        with open(records_path, "r", encoding="utf-8") as f:
            records = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        records = {}

    changed = False
    if metrics.peak_aipm > records.get("peak_aipm", 0):
        records["peak_aipm"] = round(metrics.peak_aipm, 1)
        changed = True
    if metrics.peak_concurrency > records.get("peak_concurrency", 0):
        records["peak_concurrency"] = metrics.peak_concurrency
        changed = True
    if metrics.session_prompts > 0:
        leverage = metrics.session_tokens / metrics.session_prompts
        if leverage > records.get("peak_leverage", 0):
            records["peak_leverage"] = round(leverage, 1)
            changed = True

    if changed:
        records["last_updated"] = datetime.now(timezone.utc).isoformat()
        with open(records_path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2)


def run_live(
    compact: bool = False,
    poll_interval: float = 2.0,
    include_history: bool = False,
    idle_timeout: int = 300,
):
    """Run the live dashboard loop.

    Args:
        compact: Use single-line compact display mode.
        poll_interval: Seconds between polls.
        include_history: If True, ingest existing data; if False, start fresh.
    """
    console = Console()
    poller = ClaudeCodePoller()
    engine = MetricsEngine()

    if include_history:
        messages = poller.poll()
        engine.ingest(messages)
        console.print(f"[dim]Loaded {len(messages)} existing messages[/dim]")
    else:
        poller.skip_existing()

    running = True

    def handle_signal(sig, frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, handle_signal)

    console.print("[bright_blue bold]\u25c8 MOTIF LIVE[/bright_blue bold] \u2014 watching for AI activity...")
    if idle_timeout > 0:
        console.print(f"[dim]Polling every {poll_interval}s | Idle timeout: {idle_timeout}s | Ctrl+C to stop[/dim]\n")
    else:
        console.print(f"[dim]Polling every {poll_interval}s | Idle timeout: disabled | Ctrl+C to stop[/dim]\n")

    try:
        while running:
            idle_triggered = False

            with Live(console=console, refresh_per_second=1, vertical_overflow="crop") as live:
                while running:
                    new_messages = poller.poll()
                    if new_messages:
                        engine.ingest(new_messages)

                    metrics = engine.compute()

                    if compact:
                        live.update(render_compact(metrics))
                    else:
                        live.update(render_full(metrics))

                    # Check for idle timeout
                    if (idle_timeout > 0
                            and engine.last_activity_timestamp > 0
                            and engine.session_tokens > 0):
                        idle_seconds = time.time() - engine.last_activity_timestamp
                        if idle_seconds >= idle_timeout:
                            idle_triggered = True
                            break

                    time.sleep(poll_interval)

            if not idle_triggered:
                break

            # Idle timeout — show summary and prompt
            final = engine.compute()
            console.print()
            console.print(render_summary(final))
            save_session(final)
            console.print(f"[dim]Session saved to ~/.motif/sessions/[/dim]\n")

            try:
                answer = console.input("[bold]Start new session?[/bold] [dim]\\[Y/n][/dim] ").strip().lower()
            except (KeyboardInterrupt, EOFError):
                answer = "n"

            if answer in ("", "y", "yes"):
                engine.reset()
                console.print("\n[bright_blue bold]\u25c8 MOTIF LIVE[/bright_blue bold] \u2014 new session started, watching for AI activity...\n")
            else:
                running = False

    except KeyboardInterrupt:
        pass

    # Show session summary on manual exit (Ctrl+C)
    final = engine.compute()
    if final.session_tokens > 0:
        console.print()
        console.print(render_summary(final))
        save_session(final)
        console.print(f"[dim]Session saved to ~/.motif/sessions/[/dim]")
    else:
        console.print("\n[dim]No AI activity detected during this session.[/dim]")
