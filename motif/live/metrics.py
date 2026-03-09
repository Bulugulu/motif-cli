"""Real-time AIPM and concurrency metrics computation."""

import time
from collections import deque
from dataclasses import dataclass, field

from .poller import Message


@dataclass
class LiveMetrics:
    """Current snapshot of live metrics."""
    concurrency: int = 0
    aipm: float = 0.0  # Current AIPM — short rolling window (speedometer)
    session_aipm: float = 0.0  # Session AIPM — session tokens / session minutes (trip avg)
    aipm_per_agent: float = 0.0
    session_tokens: int = 0  # tokens since dashboard launch
    session_prompts: int = 0  # prompts since dashboard launch
    peak_aipm: float = 0.0
    peak_aipm_ago: str = ""
    peak_concurrency: int = 0
    session_start: float = 0.0
    session_duration_str: str = "0m"
    active_sessions: set = field(default_factory=set)
    idle_capacity: bool = False


# Color thresholds — calibrated from real single-agent Claude Code data
# Peak single-agent minute: ~10k tok/m, p95: ~4k, median: ~100
THRESHOLDS = {
    "concurrency": {"red": 0, "yellow": 1, "green": 2, "purple": 4},
    "aipm": {"red": 0, "yellow": 500, "green": 2000, "purple": 8000},
    "aipm_per_agent": {"red": 0, "yellow": 500, "green": 2000, "purple": 8000},
}


def get_color(metric: str, value: float) -> str:
    """Return color name based on threshold."""
    t = THRESHOLDS.get(metric, {})
    if value >= t.get("purple", float("inf")):
        return "purple"
    if value >= t.get("green", float("inf")):
        return "green"
    if value >= t.get("yellow", float("inf")):
        return "yellow"
    return "red"


def get_color_emoji(metric: str, value: float) -> str:
    """Return colored circle emoji for a metric value."""
    color = get_color(metric, value)
    return {"red": "[red]\u25cf[/red]", "yellow": "[yellow]\u25cf[/yellow]",
            "green": "[green]\u25cf[/green]", "purple": "[magenta]\u25cf[/magenta]"}[color]


def _parse_timestamp(ts: str) -> float:
    """Parse an ISO 8601 timestamp to epoch seconds."""
    try:
        from datetime import datetime, timezone
        ts = ts.replace("Z", "+00:00")
        dt = datetime.fromisoformat(ts)
        return dt.timestamp()
    except (ValueError, TypeError):
        return time.time()


class MetricsEngine:
    """Computes rolling AIPM metrics from a stream of messages."""

    ACTIVE_THRESHOLD = 30  # seconds — AI must have produced tokens this recently to count as "working"
    CURRENT_WINDOW = 15  # seconds — short rolling window for "current AIPM" speedometer

    def __init__(self):
        self._token_events: deque[tuple[float, int, str]] = deque()  # (time, tokens, session_id)
        self._prompt_times: deque[float] = deque()
        self._session_last_ai: dict[str, float] = {}  # session_id -> last AI token time
        self._request_tokens: dict[str, int] = {}  # request_id -> highest output_tokens seen
        self.session_tokens: int = 0  # only tokens since dashboard launch (deduplicated)
        self.session_prompts: int = 0  # only prompts since dashboard launch
        self.peak_aipm: float = 0.0
        self.peak_aipm_time: float = 0.0
        self.peak_concurrency: int = 0
        self.session_start: float = time.time()

    def ingest(self, messages: list[Message]):
        """Process new messages into the metrics engine.

        Token counts are cumulative within a single API response (requestId).
        Each JSONL line for the same request reports the running total so far.
        We deduplicate by only counting the *increase* over the previous
        highest value seen for that requestId.
        """
        now = time.time()

        for msg in messages:
            msg_time = _parse_timestamp(msg.timestamp) if msg.timestamp else now

            if msg.type == "assistant" and msg.output_tokens > 0:
                # Deduplicate cumulative token counts within same API response
                req_id = msg.request_id
                prev = self._request_tokens.get(req_id, 0) if req_id else 0
                if msg.output_tokens > prev:
                    delta = msg.output_tokens - prev
                    if req_id:
                        self._request_tokens[req_id] = msg.output_tokens
                    self._token_events.append((msg_time, delta, msg.session_id))
                    if msg_time >= self.session_start:
                        self.session_tokens += delta

                self._session_last_ai[msg.session_id] = max(
                    self._session_last_ai.get(msg.session_id, 0), msg_time
                )

            if msg.type == "user":
                self._prompt_times.append(msg_time)
                if msg_time >= self.session_start:
                    self.session_prompts += 1

    def compute(self) -> LiveMetrics:
        """Compute current metrics snapshot."""
        now = time.time()

        # --- Concurrency: AI produced tokens in last ACTIVE_THRESHOLD seconds ---
        concurrency = sum(
            1 for t in self._session_last_ai.values()
            if now - t < self.ACTIVE_THRESHOLD
        )

        # --- Current AIPM: tokens in last CURRENT_WINDOW seconds, extrapolated to per-minute ---
        current_cutoff = now - self.CURRENT_WINDOW
        current_tokens = sum(
            tokens for t, tokens, _ in self._token_events
            if t >= current_cutoff
        )
        aipm = (current_tokens / self.CURRENT_WINDOW) * 60

        # --- Session AIPM: tokens since launch / minutes since launch ---
        session_elapsed = now - self.session_start
        session_minutes = session_elapsed / 60 if session_elapsed > 60 else 1
        session_aipm = self.session_tokens / session_minutes

        # --- Per-agent: current AIPM / concurrent agents ---
        aipm_per_agent = aipm / concurrency if concurrency > 0 else 0

        # --- Peaks ---
        if aipm > self.peak_aipm:
            self.peak_aipm = aipm
            self.peak_aipm_time = now

        if concurrency > self.peak_concurrency:
            self.peak_concurrency = concurrency

        # Peak ago string
        if self.peak_aipm_time > 0:
            ago = int(now - self.peak_aipm_time)
            if ago < 60:
                peak_ago = f"{ago}s ago"
            else:
                peak_ago = f"{ago // 60}m ago"
        else:
            peak_ago = ""

        # Session duration
        elapsed = int(now - self.session_start)
        if elapsed < 3600:
            duration = f"{elapsed // 60}m"
        else:
            duration = f"{elapsed // 3600}h {(elapsed % 3600) // 60}m"

        # Idle capacity: agents exist but aren't fully loaded
        idle = concurrency > 0 and aipm_per_agent < THRESHOLDS["aipm_per_agent"]["yellow"]

        # Prune token events older than 5 min (no metric needs them)
        prune_cutoff = now - 300
        while self._token_events and self._token_events[0][0] < prune_cutoff:
            self._token_events.popleft()

        return LiveMetrics(
            concurrency=concurrency,
            aipm=aipm,
            session_aipm=session_aipm,
            aipm_per_agent=aipm_per_agent,
            session_tokens=self.session_tokens,
            session_prompts=self.session_prompts,
            peak_aipm=self.peak_aipm,
            peak_aipm_ago=peak_ago,
            peak_concurrency=self.peak_concurrency,
            session_start=self.session_start,
            session_duration_str=duration,
            active_sessions={
                sid for sid, t in self._session_last_ai.items()
                if now - t < self.ACTIVE_THRESHOLD
            },
            idle_capacity=idle,
        )
