"""Main loop for the live dashboard."""

import time
import signal

from rich.console import Console
from rich.live import Live

from .poller import ClaudeCodePoller
from .metrics import MetricsEngine
from .display import render_full, render_compact, render_summary


def run_live(
    compact: bool = False,
    poll_interval: float = 2.0,
    include_history: bool = False,
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
    console.print(f"[dim]Polling every {poll_interval}s | Ctrl+C to stop[/dim]\n")

    try:
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

                time.sleep(poll_interval)

    except KeyboardInterrupt:
        pass

    # Show session summary
    final = engine.compute()
    if final.total_tokens > 0:
        console.print()
        console.print(render_summary(final))
    else:
        console.print("\n[dim]No AI activity detected during this session.[/dim]")
