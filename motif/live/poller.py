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


class CopilotCliPoller:
    """Polls Copilot CLI JSONL files for new messages.

    Watches ~/.copilot/session-state/ for active session files and reads
    new lines as they're appended.
    """

    def __init__(self, copilot_path: Optional[Path] = None):
        self.copilot_path = copilot_path or (Path.home() / ".copilot")
        self.sessions: dict[str, SessionState] = {}
        self._discovered_files: set[str] = set()
        self._current_model: dict[str, str] = {}  # session_id -> current model

    def discover_sessions(self) -> list[Path]:
        """Find all events.jsonl session files."""
        session_state_dir = self.copilot_path / "session-state"
        if not session_state_dir.exists():
            return []
        files = []
        # New format: {id}/events.jsonl subdirectories
        for subdir in session_state_dir.iterdir():
            if subdir.is_dir():
                events_file = subdir / "events.jsonl"
                if events_file.exists():
                    files.append(events_file)
        # Old format: flat .jsonl files
        for f in session_state_dir.iterdir():
            if f.is_file() and f.suffix == ".jsonl":
                files.append(f)
        return files

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
                    last_size=0,
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

            try:
                with open(state.path, "r", encoding="utf-8") as f:
                    f.seek(state.last_size)
                    new_data = f.read()
                state.last_size = current_size
            except OSError:
                continue

            for line in new_data.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue

                msg = self._parse_record(record, state)
                if msg:
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
        """Advance all file pointers to current end — only track NEW data.

        Still reads the session.start event from each file to capture
        session_id and project context needed for future live messages.
        """
        for path in self.discover_sessions():
            key = str(path)
            try:
                size = path.stat().st_size
            except OSError:
                size = 0
            state = SessionState(path=path, last_size=size)
            self.sessions[key] = state
            self._discovered_files.add(key)

            # Read first few lines to extract session metadata
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            record = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if record.get("type") == "session.start":
                            data = record.get("data", {})
                            sid = data.get("sessionId", "")
                            if sid:
                                state.session_id = sid
                            ctx = data.get("context", {})
                            cwd = ctx.get("cwd", "")
                            if cwd:
                                state.project = cwd.rstrip("/\\").rsplit(
                                    "/", 1
                                )[-1].rsplit("\\", 1)[-1].lower()
                            break
            except OSError:
                pass

    def _parse_record(
        self, record: dict, state: SessionState
    ) -> Optional[Message]:
        """Parse a Copilot CLI event into a Message."""
        event_type = record.get("type")
        data = record.get("data", {})
        timestamp = record.get("timestamp", "")
        session_id = state.session_id or "unknown"
        project = state.project or "unknown"

        if event_type == "session.start":
            sid = data.get("sessionId", "")
            if sid:
                state.session_id = sid
            context = data.get("context", {})
            cwd = context.get("cwd", "")
            if cwd:
                state.project = cwd.rstrip("/\\").rsplit("/", 1)[-1].rsplit(
                    "\\", 1
                )[-1].lower()
            return None

        if event_type == "session.model_change":
            new_model = data.get("newModel")
            if new_model and state.session_id:
                self._current_model[state.session_id] = new_model
            return None

        if event_type == "user.message":
            content = data.get("content", "")
            return Message(
                type="user",
                timestamp=timestamp,
                session_id=state.session_id or "unknown",
                project=state.project or "unknown",
                content_chars=len(content) if isinstance(content, str) else 0,
            )

        if event_type == "assistant.message":
            content = data.get("content", "")
            parent_tcid = data.get("parentToolCallId")
            is_subagent = bool(parent_tcid)
            effective_sid = (
                f"subagent-{parent_tcid}"
                if is_subagent and parent_tcid
                else (state.session_id or "unknown")
            )
            return Message(
                type="assistant",
                timestamp=timestamp,
                session_id=effective_sid,
                project=state.project or "unknown",
                content_chars=len(content) if isinstance(content, str) else 0,
                output_tokens=data.get("outputTokens", 0) or 0,
                model=self._current_model.get(state.session_id or "", None),
                request_id=data.get("interactionId", ""),
                is_subagent=is_subagent,
            )

        if event_type == "assistant.usage":
            parent_tcid = data.get("parentToolCallId")
            is_subagent = bool(parent_tcid)
            effective_sid = (
                f"subagent-{parent_tcid}"
                if is_subagent and parent_tcid
                else (state.session_id or "unknown")
            )
            model = data.get("model") or self._current_model.get(
                state.session_id or "", None
            )
            return Message(
                type="assistant",
                timestamp=timestamp,
                session_id=effective_sid,
                project=state.project or "unknown",
                output_tokens=data.get("outputTokens", 0) or 0,
                input_tokens=data.get("inputTokens", 0) or 0,
                model=model,
                request_id=data.get("interactionId", data.get("apiCallId", "")),
                is_subagent=is_subagent,
            )

        return None
