"""
Copilot CLI Conversation Extractor

Extracts user/assistant dialogue from GitHub Copilot CLI session files.
Organizes by project and includes file reference metrics.

Session files live in ~/.copilot/session-state/ (and ~/.copilot/history-session-state/).
Two on-disk layouts are supported:
  1. New format (v0.0.342+): {session-id}/events.jsonl subdirectories
  2. Old format:             flat {session-id}.jsonl files

Exports:
- get_copilot_cli_data_path() -> Path
- extract_conversations(copilot_path: Optional[str] = None) -> list[dict]
- group_by_project(messages) -> dict[str, list[dict]]
- get_stats(messages) -> dict
"""

import json
from pathlib import Path
from typing import Optional
from collections import defaultdict
import platform


# Argument keys that carry file paths in tool execution events
_FILE_ARG_KEYS = ("path", "file_path", "file", "filePath", "target_file")


def get_copilot_cli_data_path() -> Path:
    """Get the Copilot CLI data directory path for the current OS."""
    return Path.home() / ".copilot"


def normalize_project_name(cwd: Optional[str]) -> str:
    """Extract a clean project name from working directory path."""
    if not cwd:
        return "unknown"

    # Normalize slashes
    path = cwd.replace("\\", "/")

    # Remove trailing slash
    path = path.rstrip("/")

    # Get last component (project folder name)
    parts = path.split("/")
    project = parts[-1] if parts else "unknown"

    return project.lower().strip() if project else "unknown"


def _extract_file_refs_from_args(arguments: dict) -> list[str]:
    """Extract file paths from tool execution arguments."""
    files: set[str] = set()
    if not isinstance(arguments, dict):
        return []
    for key in _FILE_ARG_KEYS:
        val = arguments.get(key)
        if val and isinstance(val, str):
            files.add(val)
    return sorted(files)


def parse_session_events(file_path: Path) -> list[dict]:
    """Parse a single Copilot CLI session JSONL file into normalised messages.

    Walks the event stream, maintaining per-session state (cwd, model) so that
    every emitted message carries the correct project and model even when those
    values are set once at the start of the session.
    """
    messages: list[dict] = []

    # Session-level state accumulated from events
    session_id: Optional[str] = None
    project: str = "unknown"
    current_model: Optional[str] = None
    session_start_time: Optional[str] = None

    # Per-assistant-turn accumulators (reset on each assistant.message)
    pending_tool_calls: list[str] = []
    pending_file_refs: set[str] = set()
    pending_tool_arg_chars: int = 0

    # Map from assistant interactionId -> index in messages list, so we can
    # back-patch the model when the authoritative assistant.usage event arrives.
    interaction_index: dict[str, int] = {}

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue

                etype = event.get("type", "")
                data = event.get("data") or {}
                timestamp = event.get("timestamp") or data.get("timestamp")

                # --- session.start -------------------------------------------
                if etype == "session.start":
                    session_id = data.get("sessionId") or session_id
                    current_model = data.get("selectedModel") or current_model
                    session_start_time = data.get("startTime") or timestamp
                    ctx = data.get("context") or {}
                    cwd = ctx.get("cwd") or ctx.get("gitRoot")
                    project = normalize_project_name(cwd)

                # --- session.model_change ------------------------------------
                elif etype == "session.model_change":
                    current_model = data.get("newModel") or current_model

                # --- user.message --------------------------------------------
                elif etype == "user.message":
                    # Reset accumulators at user-message boundary to prevent
                    # tool calls from a previous interaction leaking forward.
                    pending_tool_calls = []
                    pending_file_refs = set()
                    pending_tool_arg_chars = 0

                    content = data.get("content", "")
                    if not isinstance(content, str) or not content.strip():
                        continue
                    messages.append({
                        "role": "user",
                        "content": content.strip(),
                        "model": None,
                        "project": project,
                        "timestamp": timestamp,
                        "session_id": session_id,
                        "files_referenced": [],
                        "tool_calls": [],
                    })

                # --- tool.execution_start ------------------------------------
                elif etype == "tool.execution_start":
                    # Skip sub-agent tool calls
                    if data.get("parentToolCallId"):
                        continue
                    tool_name = data.get("toolName")
                    if tool_name:
                        pending_tool_calls.append(tool_name)
                    args = data.get("arguments") or {}
                    pending_file_refs.update(_extract_file_refs_from_args(args))
                    if isinstance(args, dict):
                        pending_tool_arg_chars += sum(
                            len(str(v)) for v in args.values()
                        )

                # --- assistant.message ---------------------------------------
                elif etype == "assistant.message":
                    # Skip sub-agent assistant messages
                    if data.get("parentToolCallId"):
                        continue

                    content = data.get("content", "")

                    # Accumulate tool args from inline toolRequests
                    tool_requests = data.get("toolRequests") or []
                    for tr in tool_requests:
                        name = tr.get("name")
                        if name:
                            pending_tool_calls.append(name)
                        tr_args = tr.get("arguments") or {}
                        pending_file_refs.update(
                            _extract_file_refs_from_args(tr_args)
                        )
                        if isinstance(tr_args, dict):
                            pending_tool_arg_chars += sum(
                                len(str(v)) for v in tr_args.values()
                            )

                    if not isinstance(content, str) or not content.strip():
                        # Tool-only turn (no prose) – don't emit a message
                        continue

                    text = content.strip()
                    msg = {
                        "role": "assistant",
                        "content": text,
                        "model": current_model,
                        "project": project,
                        "timestamp": timestamp,
                        "session_id": session_id,
                        "files_referenced": sorted(pending_file_refs),
                        "tool_calls": list(pending_tool_calls),
                        "output_chars": len(text) + pending_tool_arg_chars,
                    }
                    messages.append(msg)

                    # Record index so assistant.usage can back-patch model
                    interaction_id = data.get("interactionId")
                    if interaction_id:
                        interaction_index[interaction_id] = len(messages) - 1

                    # Reset per-turn accumulators
                    pending_tool_calls = []
                    pending_file_refs = set()
                    pending_tool_arg_chars = 0

                # --- assistant.usage -----------------------------------------
                elif etype == "assistant.usage":
                    # Skip sub-agent usage records
                    if data.get("parentToolCallId"):
                        continue
                    model = data.get("model")
                    if model:
                        current_model = model
                        # Back-patch the most recent assistant message with the
                        # authoritative model from the usage event.
                        for idx in range(len(messages) - 1, -1, -1):
                            if messages[idx]["role"] == "assistant":
                                messages[idx]["model"] = model
                                break

    except (OSError, IOError):
        return []

    # Back-patch session_start and session_end onto all messages.
    # session_start comes from the session.start event; session_end is the
    # timestamp of the last message in the session.
    if messages and session_start_time:
        last_ts = None
        for m in reversed(messages):
            if m.get("timestamp"):
                last_ts = m["timestamp"]
                break
        for m in messages:
            m["session_start"] = session_start_time
            m["session_end"] = last_ts

    return messages


def find_all_session_files(copilot_path: Path) -> list[Path]:
    """Find all session JSONL files across both storage layouts."""
    session_files: list[Path] = []

    search_dirs = [
        copilot_path / "session-state",
        copilot_path / "history-session-state",
    ]

    for base_dir in search_dirs:
        if not base_dir.exists():
            continue

        for item in base_dir.iterdir():
            try:
                # New format: {session-id}/events.jsonl
                if item.is_dir():
                    events_file = item / "events.jsonl"
                    if events_file.is_file():
                        session_files.append(events_file)
                # Old format: {session-id}.jsonl
                elif item.is_file() and item.suffix == ".jsonl":
                    session_files.append(item)
            except OSError:
                continue

    return session_files


def extract_all_conversations(copilot_path: Path) -> list[dict]:
    """Extract all conversations from all session files."""
    all_messages: list[dict] = []

    session_files = find_all_session_files(copilot_path)

    for session_file in session_files:
        try:
            messages = parse_session_events(session_file)
            all_messages.extend(messages)
        except Exception:
            continue

    def sort_key(m):
        ts = m.get("timestamp") or ""
        return ts

    all_messages.sort(key=sort_key)

    return all_messages


def extract_conversations(copilot_path: Optional[str] = None) -> list[dict]:
    """
    Main entry point: extract conversations from Copilot CLI session files.
    Auto-detects data path if not provided.
    """
    if copilot_path is None:
        path = get_copilot_cli_data_path()
    else:
        path = Path(copilot_path)
    if not path.exists():
        return []
    return extract_all_conversations(path)


def group_by_project(messages: list[dict]) -> dict[str, list[dict]]:
    """Group messages by project name."""
    projects = defaultdict(list)
    for msg in messages:
        project = msg.get("project") or "unknown"
        projects[project].append(msg)
    return dict(projects)


def get_stats(messages: list[dict]) -> dict:
    """Calculate statistics about the conversations."""
    user_msgs = [m for m in messages if m["role"] == "user"]
    asst_msgs = [m for m in messages if m["role"] == "assistant"]

    user_lengths = [len(m["content"]) for m in user_msgs]
    asst_lengths = [len(m["content"]) for m in asst_msgs]

    models_used = {}
    for m in asst_msgs:
        model = m.get("model") or "unknown"
        models_used[model] = models_used.get(model, 0) + 1

    all_files: set[str] = set()
    for m in asst_msgs:
        all_files.update(m.get("files_referenced", []))

    tool_counts: dict[str, int] = {}
    for m in asst_msgs:
        for tool in m.get("tool_calls", []):
            tool_counts[tool] = tool_counts.get(tool, 0) + 1

    sessions = set(m.get("session_id") for m in messages if m.get("session_id"))

    return {
        "total_messages": len(messages),
        "user_messages": len(user_msgs),
        "assistant_messages": len(asst_msgs),
        "avg_user_length": sum(user_lengths) / len(user_lengths) if user_lengths else 0,
        "avg_assistant_length": sum(asst_lengths) / len(asst_lengths) if asst_lengths else 0,
        "total_user_chars": sum(user_lengths),
        "total_assistant_chars": sum(asst_lengths),
        "models_used": models_used,
        "unique_files_referenced": len(all_files),
        "tool_usage": tool_counts,
        "unique_sessions": len(sessions),
    }
