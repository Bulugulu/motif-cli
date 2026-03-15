"""Poll Claude Code session files for new messages in real-time."""

import json
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SessionState:
    """Tracks polling state for a single JSONL session file."""
    path: Path
    last_size: int = 0
    session_id: Optional[str] = None
    project: Optional[str] = None


@dataclass
class Message:
    """A parsed message from a Claude Code session."""
    type: str  # "user", "assistant", "system"
    timestamp: str
    session_id: str
    project: str
    output_tokens: int = 0
    input_tokens: int = 0
    content_chars: int = 0
    model: Optional[str] = None
    request_id: str = ""  # groups chunks of the same API response
    is_subagent: bool = False


class ClaudeCodePoller:
    """Polls Claude Code JSONL files for new messages.

    Watches ~/.claude/projects/ for active session files and reads
    new lines as they're appended.
    """

    def __init__(self, claude_path: Optional[Path] = None):
        self.claude_path = claude_path or (Path.home() / ".claude")
        self.sessions: dict[str, SessionState] = {}
        self._discovered_files: set[str] = set()

    def discover_sessions(self) -> list[Path]:
        """Find all JSONL session files."""
        projects_dir = self.claude_path / "projects"
        if not projects_dir.exists():
            return []
        return list(projects_dir.rglob("*.jsonl"))

    def poll(self) -> list[Message]:
        """Poll all known sessions for new messages.

        Returns new messages since last poll.
        """
        new_messages = []

        # Discover new session files
        for path in self.discover_sessions():
            key = str(path)
            if key not in self.sessions:
                self.sessions[key] = SessionState(
                    path=path,
                    last_size=0,  # Read from beginning on first discovery
                )
                self._discovered_files.add(key)

        # Read new data from each session
        for key, state in list(self.sessions.items()):
            try:
                current_size = state.path.stat().st_size
            except OSError:
                continue

            if current_size <= state.last_size:
                continue

            # Read only the new bytes
            try:
                with open(state.path, "r", encoding="utf-8") as f:
                    f.seek(state.last_size)
                    new_data = f.read()
                state.last_size = current_size
            except OSError:
                continue

            is_subagent = "subagents" in str(state.path)

            for line in new_data.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue

                msg = self._parse_record(record, is_subagent)
                if msg:
                    # Subagents share their parent's sessionId, so use the
                    # filename as identity instead — each subagent gets its
                    # own JSONL file (e.g. agent-aa07d56.jsonl)
                    if is_subagent:
                        msg.session_id = state.path.stem

                    if not state.session_id:
                        state.session_id = msg.session_id
                    if not state.project:
                        state.project = msg.project
                    new_messages.append(msg)

        return new_messages

    def get_active_session_ids(self, window_seconds: float = 300) -> set[str]:
        """Return session IDs that have been active recently."""
        cutoff = time.time() - window_seconds
        active = set()
        for state in self.sessions.values():
            try:
                if state.path.stat().st_mtime > cutoff and state.session_id:
                    active.add(state.session_id)
            except OSError:
                continue
        return active

    def skip_existing(self):
        """Advance all file pointers to current end — only track NEW data."""
        for path in self.discover_sessions():
            key = str(path)
            try:
                size = path.stat().st_size
            except OSError:
                size = 0
            self.sessions[key] = SessionState(path=path, last_size=size)
            self._discovered_files.add(key)

    def _parse_record(self, record: dict, is_subagent: bool) -> Optional[Message]:
        """Parse a JSONL record into a Message."""
        msg_type = record.get("type")

        if msg_type not in ("user", "assistant"):
            return None

        message_data = record.get("message", {})
        usage = message_data.get("usage", {})

        # Calculate content size
        content = message_data.get("content", "")
        if isinstance(content, list):
            content_chars = sum(
                len(block.get("text", ""))
                for block in content
                if isinstance(block, dict) and block.get("type") == "text"
            )
        elif isinstance(content, str):
            content_chars = len(content)
        else:
            content_chars = 0

        # Extract project from cwd
        cwd = record.get("cwd", "")
        project = cwd.rstrip("/\\").rsplit("/", 1)[-1] if cwd else "unknown"

        return Message(
            type=msg_type,
            timestamp=record.get("timestamp", ""),
            session_id=record.get("sessionId", "unknown"),
            project=project.lower(),
            output_tokens=usage.get("output_tokens", 0),
            input_tokens=usage.get("input_tokens", 0),
            content_chars=content_chars,
            model=message_data.get("model"),
            request_id=record.get("requestId", message_data.get("id", "")),
            is_subagent=is_subagent,
        )
