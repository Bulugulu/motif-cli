"""
VS Code Copilot Chat Conversation Extractor

Extracts user/assistant dialogue from VS Code Copilot Chat session files.
Supports two storage formats:
  1. JSON/JSONL files in workspaceStorage/<id>/chat/ directories
  2. VSCDB (SQLite) databases with chat data in ItemTable

Exports:
- get_copilot_vscode_data_paths() -> list[tuple[Path, str]]
- extract_conversations(storage_paths=None) -> list[dict]
- group_by_project(messages) -> dict[str, list[dict]]
- get_stats(messages) -> dict
"""

import json
import sqlite3
import os
import platform
from pathlib import Path
from typing import Optional
from datetime import datetime
from collections import defaultdict
from urllib.parse import unquote


# ---------------------------------------------------------------------------
# STORAGE PATHS
# ---------------------------------------------------------------------------

def get_copilot_vscode_data_paths() -> list[tuple[Path, str]]:
    """Get all VS Code workspace storage directories for the current OS.

    Returns a list of (path, edition) tuples where edition is 'stable'
    or 'insider'.
    """
    system = platform.system()
    home = Path.home()

    if system == "Windows":
        appdata = os.environ.get("APPDATA", "")
        if not appdata:
            return []
        base = Path(appdata)
        candidates = [
            (base / "Code" / "User" / "workspaceStorage", "stable"),
            (base / "Code - Insiders" / "User" / "workspaceStorage", "insider"),
        ]
    elif system == "Darwin":
        support = home / "Library" / "Application Support"
        candidates = [
            (support / "Code" / "User" / "workspaceStorage", "stable"),
            (support / "Code - Insiders" / "User" / "workspaceStorage", "insider"),
        ]
    else:  # Linux
        config = home / ".config"
        candidates = [
            (config / "Code" / "User" / "workspaceStorage", "stable"),
            (config / "Code - Insiders" / "User" / "workspaceStorage", "insider"),
        ]

    return [(p, edition) for p, edition in candidates if p.exists()]


# ---------------------------------------------------------------------------
# WORKSPACE / PROJECT DETECTION
# ---------------------------------------------------------------------------

def _read_workspace_project(workspace_dir: Path) -> Optional[str]:
    """Read workspace.json to extract the project name."""
    ws_file = workspace_dir / "workspace.json"
    if not ws_file.exists():
        return None

    try:
        with open(ws_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

    folder = data.get("folder", "")
    if not folder:
        return None

    # URL-decode and strip file:// prefix
    if folder.startswith("file:///"):
        folder = folder[len("file:///"):]
    elif folder.startswith("file://"):
        folder = folder[len("file://"):]

    folder = unquote(folder)

    # Normalize and extract last path component
    folder = folder.replace("\\", "/").rstrip("/")
    parts = folder.split("/")
    project = parts[-1] if parts else None

    if project:
        return project.lower().strip()
    return None


# ---------------------------------------------------------------------------
# RESPONSE CONTENT PARSING
# ---------------------------------------------------------------------------

def _parse_response_items(items: list) -> tuple[str, list[str], list[str], int]:
    """Parse response items into text, files_referenced, tool_calls, output_chars.

    VS Code Copilot Chat stores response items in two formats:

    Format A (v3 ISerializableChatData with nested content):
      - kind == "markdownContent" → content.value
      - kind == "codeBlockContent" → content.value (output_chars only)
      - kind == "thinkingContent" → skip
      - kind == "toolInvocation" → toolName
      - kind == "inlineReference" → name

    Format B (current VS Code agent mode, flat items):
      - No kind, has "value" string → assistant text
      - kind == "thinking" → skip
      - kind == "toolInvocationSerialized" → tool call
      - kind == "prepareToolInvocation" → toolName
      - kind == "inlineReference" → inlineReference.fsPath
      - kind == "codeblockUri" / "textEditGroup" → file reference from uri.fsPath
      - kind == "mcpServersStarting" / "undoStop" → skip

    Returns (text, files_referenced, tool_calls, output_chars).
    """
    texts = []
    files_referenced = set()
    tool_calls = []
    output_chars = 0

    for item in items:
        if not isinstance(item, dict):
            continue

        kind = item.get("kind", "")

        # --- Format A: nested content objects ---
        if kind == "markdownContent":
            content = item.get("content", {})
            value = content.get("value", "") if isinstance(content, dict) else ""
            if value:
                texts.append(value)
                output_chars += len(value)
            continue

        if kind == "codeBlockContent":
            content = item.get("content", {})
            value = content.get("value", "") if isinstance(content, dict) else ""
            output_chars += len(value)
            continue

        if kind == "thinkingContent":
            continue

        if kind == "toolInvocation":
            tool_name = item.get("toolName", "")
            if tool_name:
                tool_calls.append(tool_name)
            continue

        # --- Format B: flat value items (current VS Code agent mode) ---
        if kind == "thinking":
            continue

        if kind == "toolInvocationSerialized":
            tool_name = item.get("toolName", "")
            if tool_name:
                tool_calls.append(tool_name)
            continue

        if kind == "prepareToolInvocation":
            tool_name = item.get("toolName", "")
            if tool_name:
                tool_calls.append(tool_name)
            continue

        if kind == "inlineReference":
            # Format A: name field
            name = item.get("name", "")
            if name:
                files_referenced.add(name)
            # Format B: inlineReference object with fsPath
            ref = item.get("inlineReference", {})
            if isinstance(ref, dict):
                fspath = ref.get("fsPath", "")
                if fspath:
                    files_referenced.add(fspath)
            continue

        if kind in ("codeblockUri", "textEditGroup"):
            uri = item.get("uri", {})
            if isinstance(uri, dict):
                fspath = uri.get("fsPath", "")
                if fspath:
                    files_referenced.add(fspath)
            continue

        if kind in ("mcpServersStarting", "undoStop", "progressMessage"):
            continue

        # Items with no kind but a "value" string → assistant text (Format B)
        if not kind and "value" in item:
            value = item.get("value", "")
            if isinstance(value, str) and value.strip():
                texts.append(value)
                output_chars += len(value)
            continue

    combined_text = "\n\n".join(texts) if texts else ""
    return combined_text, sorted(files_referenced), tool_calls, output_chars


def _epoch_ms_to_iso(epoch_ms) -> Optional[str]:
    """Convert epoch milliseconds to UTC ISO 8601 string."""
    if not epoch_ms or not isinstance(epoch_ms, (int, float)):
        return None
    try:
        from datetime import timezone
        dt = datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc)
        return dt.isoformat()
    except (OSError, ValueError, OverflowError):
        return None


# ---------------------------------------------------------------------------
# SESSION PARSING: ISerializableChatData v3
# ---------------------------------------------------------------------------

def _parse_chat_session(data: dict, project: Optional[str]) -> list[dict]:
    """Parse an ISerializableChatData session dict into normalized messages."""
    messages = []

    session_id = data.get("sessionId")
    creation_date = _epoch_ms_to_iso(data.get("creationDate"))
    requests = data.get("requests", [])

    if not requests:
        return messages

    # Collect all timestamps to derive session_start/session_end
    all_timestamps = []
    if creation_date:
        all_timestamps.append(creation_date)

    for request in requests:
        if not isinstance(request, dict):
            continue

        timestamp = _epoch_ms_to_iso(request.get("timestamp"))
        if timestamp:
            all_timestamps.append(timestamp)
        model_id = request.get("modelId") or None

        # --- User message ---
        message_obj = request.get("message", {})
        if isinstance(message_obj, dict):
            user_text = message_obj.get("text", "")
        elif isinstance(message_obj, str):
            user_text = message_obj
        else:
            user_text = ""

        if user_text and user_text.strip():
            messages.append({
                "role": "user",
                "content": user_text.strip(),
                "model": None,
                "project": project or "unknown",
                "timestamp": timestamp,
                "session_id": session_id,
                "files_referenced": [],
                "tool_calls": [],
                "output_chars": 0,
            })

        # --- Assistant response ---
        response_obj = request.get("response", {})

        # Response can be a list directly (current format) or a dict with "value" key
        if isinstance(response_obj, list):
            response_items = response_obj
        elif isinstance(response_obj, dict):
            response_items = response_obj.get("value", [])
        else:
            continue

        if not isinstance(response_items, list) or not response_items:
            continue

        text, files_ref, tools, out_chars = _parse_response_items(response_items)

        if text.strip():
            messages.append({
                "role": "assistant",
                "content": text.strip(),
                "model": model_id,
                "project": project or "unknown",
                "timestamp": timestamp,
                "session_id": session_id,
                "files_referenced": files_ref,
                "tool_calls": tools,
                "output_chars": out_chars,
            })
        elif tools or files_ref:
            # Preserve tool-only assistant turns (no prose but has tool calls)
            messages.append({
                "role": "assistant",
                "content": "",
                "model": model_id,
                "project": project or "unknown",
                "timestamp": timestamp,
                "session_id": session_id,
                "files_referenced": files_ref,
                "tool_calls": tools,
                "output_chars": out_chars,
            })

    # Back-patch session_start/session_end onto all messages
    if messages and all_timestamps:
        session_start = min(all_timestamps)
        session_end = max(all_timestamps)
        for m in messages:
            m["session_start"] = session_start
            m["session_end"] = session_end

    return messages


# ---------------------------------------------------------------------------
# JSON / JSONL FILE EXTRACTION
# ---------------------------------------------------------------------------

def _extract_from_json_files(workspace_dir: Path, project: Optional[str]) -> list[dict]:
    """Extract conversations from JSON/JSONL files in chatSessions/ or chat/ subdirectories."""
    messages = []

    for subdir_name in ("chatSessions", "chat"):
        chat_dir = workspace_dir / subdir_name
        if not chat_dir.exists() or not chat_dir.is_dir():
            continue

        for filepath in chat_dir.iterdir():
            if not filepath.is_file():
                continue
            suffix = filepath.suffix.lower()
            if suffix not in (".json", ".jsonl"):
                continue

            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    raw = f.read().strip()
            except OSError:
                continue

            if not raw:
                continue

            if suffix == ".jsonl":
                for line in raw.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(data, dict) and "requests" in data:
                        messages.extend(_parse_chat_session(data, project))
            else:
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if isinstance(data, dict) and "requests" in data:
                    messages.extend(_parse_chat_session(data, project))

    return messages


# ---------------------------------------------------------------------------
# VSCDB (SQLite) EXTRACTION
# ---------------------------------------------------------------------------

def _extract_from_vscdb(db_path: Path, project: Optional[str]) -> list[dict]:
    """Extract conversations from a state.vscdb SQLite database.

    Looks for ItemTable keys matching interactive-session-* or chat.data.*
    patterns. Values are JSON strings with ISerializableChatData structure.
    """
    messages = []

    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro&immutable=1", uri=True)
    except (sqlite3.Error, OSError):
        return []

    try:
        cursor = conn.cursor()

        # Check that ItemTable exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='ItemTable'"
        )
        if not cursor.fetchone():
            conn.close()
            return []

        cursor.execute(
            "SELECT key, value FROM ItemTable "
            "WHERE key LIKE 'interactive-session-%' OR key LIKE 'chat.data.%'"
        )

        for key, value in cursor.fetchall():
            if not value:
                continue
            if isinstance(value, bytes):
                value = value.decode("utf-8", errors="replace")
            try:
                data = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                continue

            if isinstance(data, dict) and "requests" in data:
                messages.extend(_parse_chat_session(data, project))

    except sqlite3.Error:
        pass
    finally:
        conn.close()

    return messages


# ---------------------------------------------------------------------------
# WORKSPACE SCANNING
# ---------------------------------------------------------------------------

def _extract_from_workspace(workspace_dir: Path) -> list[dict]:
    """Extract all conversations from a single workspace storage directory."""
    project = _read_workspace_project(workspace_dir)

    messages = []

    # Strategy 1: JSON/JSONL files in chat/ subdirectory
    messages.extend(_extract_from_json_files(workspace_dir, project))

    # Strategy 2: VSCDB databases
    for db_name in ("state.vscdb", "state.vscdb.backup"):
        db_path = workspace_dir / db_name
        if db_path.exists() and db_path.is_file():
            messages.extend(_extract_from_vscdb(db_path, project))

    return messages


def _extract_from_storage_root(storage_root: Path) -> list[dict]:
    """Scan all workspace subdirectories under a workspaceStorage root."""
    messages = []

    if not storage_root.exists() or not storage_root.is_dir():
        return messages

    for workspace_dir in storage_root.iterdir():
        if not workspace_dir.is_dir():
            continue
        try:
            messages.extend(_extract_from_workspace(workspace_dir))
        except Exception:
            continue

    return messages


def _extract_from_global_sessions(global_storage: Path) -> list[dict]:
    """Extract conversations from globalStorage/emptyWindowChatSessions/.

    These are sessions opened without a workspace folder.
    """
    messages = []

    sessions_dir = global_storage / "emptyWindowChatSessions"
    if not sessions_dir.exists() or not sessions_dir.is_dir():
        return messages

    for filepath in sessions_dir.iterdir():
        if not filepath.is_file():
            continue
        suffix = filepath.suffix.lower()
        if suffix not in (".json", ".jsonl"):
            continue

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                raw = f.read().strip()
        except OSError:
            continue

        if not raw:
            continue

        if suffix == ".jsonl":
            for line in raw.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(data, dict) and "requests" in data:
                    messages.extend(_parse_chat_session(data, "unknown"))
        else:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict) and "requests" in data:
                messages.extend(_parse_chat_session(data, "unknown"))

    return messages


# ---------------------------------------------------------------------------
# PUBLIC API
# ---------------------------------------------------------------------------

def extract_conversations(storage_paths=None) -> list[dict]:
    """Main entry point: extract conversations from VS Code Copilot Chat.

    Args:
        storage_paths: Optional list of (Path, edition) tuples. If None,
            auto-detects using get_copilot_vscode_data_paths().

    Returns:
        List of normalized message dicts sorted by timestamp.
    """
    if storage_paths is None:
        storage_paths = get_copilot_vscode_data_paths()

    all_messages = []
    scanned_global_dirs = set()

    for storage_root, _edition in storage_paths:
        all_messages.extend(_extract_from_storage_root(storage_root))

        # Also check globalStorage sibling for emptyWindowChatSessions
        global_storage = storage_root.parent.parent / "globalStorage"
        resolved = str(global_storage.resolve())
        if global_storage.exists() and resolved not in scanned_global_dirs:
            scanned_global_dirs.add(resolved)
            all_messages.extend(_extract_from_global_sessions(global_storage))

    # Sort by timestamp
    def sort_key(m):
        return m.get("timestamp") or ""

    all_messages.sort(key=sort_key)

    return all_messages


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

    all_files = set()
    for m in asst_msgs:
        all_files.update(m.get("files_referenced", []))

    tool_counts = {}
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
