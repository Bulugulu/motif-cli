"""
Cursor Conversation Extractor

Extracts user/assistant dialogue from Cursor's state database.
Uses two extraction strategies:
  1. Primary: composerData + bubbleId (Cursor's current storage format)
  2. Fallback: agentKv:blob (older format, for backward compatibility)

Exports:
- get_cursor_db_path() -> Path
- extract_conversations(db_path: Optional[str] = None) -> list[dict]
- group_by_project(messages) -> dict[str, list[dict]]
- get_stats(messages) -> dict
"""

import sqlite3
import json
import re
from pathlib import Path
from typing import Optional
from datetime import datetime, timedelta
from collections import defaultdict
from urllib.parse import unquote
import os
import platform


# Known parent directories for code projects
_PROJECT_PARENTS = frozenset({
    "github", "repos", "projects", "workspace", "workspaces",
    "dev", "code", "sites", "src",
})

# File extensions — used to detect when we accidentally grabbed a filename
_FILE_EXTENSIONS = frozenset({
    ".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".md", ".html", ".css",
    ".yaml", ".yml", ".toml", ".rs", ".go", ".java", ".rb", ".sh",
    ".jsonl", ".csv", ".xml", ".sql", ".env", ".lock", ".cfg",
})


def get_cursor_db_path() -> Path:
    """Get the Cursor state.vscdb path for the current OS."""
    system = platform.system()
    if system == "Windows":
        appdata = os.environ.get("APPDATA", "")
        return Path(appdata) / "Cursor" / "User" / "globalStorage" / "state.vscdb"
    elif system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "Cursor" / "User" / "globalStorage" / "state.vscdb"
    else:
        return Path.home() / ".config" / "Cursor" / "User" / "globalStorage" / "state.vscdb"


def extract_project_from_path(fspath: str) -> Optional[str]:
    """Extract project name from an absolute file/folder path.

    Strategy: find the first known project-parent directory and take
    the folder immediately after it. Falls back to heuristics.
    """
    if not fspath or len(fspath) < 5:
        return None

    path = fspath.replace("\\", "/").rstrip("/")

    # URL-decode if needed
    if "%3A" in path or "%3a" in path or "%2F" in path:
        path = unquote(path)

    # Strip leading / from /c:/ format
    if re.match(r"^/[a-zA-Z]:", path):
        path = path[1:]

    parts = path.split("/")

    # Strategy 1: find a known project-parent directory
    for i, part in enumerate(parts):
        if part.lower() in _PROJECT_PARENTS and i + 1 < len(parts):
            candidate = parts[i + 1]
            if _is_valid_project_name(candidate):
                return candidate

    # Strategy 2: for Windows paths like c:/Users/<user>/<project>/...
    # take 4th segment if it looks like a project
    if len(parts) >= 4 and re.match(r"^[a-zA-Z]:$", parts[0]):
        # c: / Users / username / <project> / ...
        if parts[1].lower() == "users" and len(parts) >= 5:
            candidate = parts[3]  # after Users/<username>
            if candidate.lower() in ("documents", "desktop", "downloads"):
                # One more level: Documents/<project>/...
                if len(parts) >= 6:
                    candidate = parts[4]
                    if candidate.lower() in _PROJECT_PARENTS:
                        if len(parts) >= 7:
                            candidate = parts[5]
                    if _is_valid_project_name(candidate):
                        return candidate
            elif _is_valid_project_name(candidate):
                return candidate

    # Strategy 3: for macOS/Linux paths like /Users/<user>/<project>/...
    if len(parts) >= 4 and (parts[1].lower() in ("users", "home")):
        candidate = parts[3]
        if candidate.lower() in ("documents", "desktop", "projects"):
            if len(parts) >= 5:
                candidate = parts[4]
                if candidate.lower() in _PROJECT_PARENTS:
                    if len(parts) >= 6:
                        candidate = parts[5]
        if _is_valid_project_name(candidate):
            return candidate

    return None


def _is_valid_project_name(name: str) -> bool:
    """Check if a string looks like a valid project name (not a filename or garbage)."""
    if not name or len(name) > 80:
        return False
    # Reject if it looks like a file (has extension)
    lower = name.lower()
    for ext in _FILE_EXTENSIONS:
        if lower.endswith(ext):
            return False
    # Reject very short names (likely not a project)
    if len(name) < 2:
        return False
    # Reject names that are clearly not project folders
    if lower in ("users", "user", "home", "var", "tmp", "etc", "bin", "lib", "opt"):
        return False
    return True


# ---------------------------------------------------------------------------
# PRIMARY EXTRACTION: composerData + bubbleId
# ---------------------------------------------------------------------------

def _extract_from_composer_data(conn: sqlite3.Connection) -> list[dict]:
    """Extract conversations using composerData + bubbleId tables.

    This is Cursor's current storage format where:
    - composerData:<uuid> holds session metadata + ordered bubble list
    - bubbleId:<uuid>:<bubble_uuid> holds individual message content
    """
    cursor = conn.cursor()

    cursor.execute("SELECT key, value FROM cursorDiskKV WHERE key LIKE 'composerData:%'")
    all_composers = cursor.fetchall()

    messages = []

    for comp_key, comp_val in all_composers:
        if isinstance(comp_val, bytes):
            comp_val = comp_val.decode("utf-8", errors="replace")
        try:
            comp_data = json.loads(comp_val)
        except (json.JSONDecodeError, TypeError):
            continue

        conv_id = comp_data.get("composerId", comp_key.replace("composerData:", ""))
        created_at = comp_data.get("createdAt")
        last_updated_at = comp_data.get("lastUpdatedAt")
        timestamp = None
        session_start = None
        session_end = None
        if created_at and isinstance(created_at, (int, float)):
            try:
                start_dt = datetime.fromtimestamp(created_at / 1000)
                timestamp = start_dt.isoformat()
                session_start = start_dt.isoformat()
            except (OSError, ValueError):
                pass
        if last_updated_at and isinstance(last_updated_at, (int, float)):
            try:
                session_end = datetime.fromtimestamp(last_updated_at / 1000).isoformat()
            except (OSError, ValueError):
                pass

        # Detect project from composerData context
        project = _detect_project_from_composer(comp_data)

        # Get ordered bubble list
        fch = comp_data.get("fullConversationHeadersOnly", [])
        if not fch:
            continue
        bubble_count = len(fch)

        # Estimate session_end from bubble count when lastUpdatedAt is missing
        if session_start and not session_end:
            try:
                start_dt = datetime.fromisoformat(session_start)
                duration_min = max(2, bubble_count * 1.5)
                session_end = (start_dt + timedelta(minutes=duration_min)).isoformat()
            except (ValueError, TypeError):
                pass

        for entry in fch:
            if not isinstance(entry, dict):
                continue

            bubble_type = entry.get("type")
            bubble_id = entry.get("bubbleId")
            if not bubble_id:
                continue

            # Read the full bubble
            cursor.execute(
                "SELECT value FROM cursorDiskKV WHERE key = ?",
                (f"bubbleId:{conv_id}:{bubble_id}",)
            )
            brow = cursor.fetchone()
            if not brow:
                continue

            bval = brow[0]
            if isinstance(bval, bytes):
                bval = bval.decode("utf-8", errors="replace")
            try:
                bdata = json.loads(bval)
            except (json.JSONDecodeError, TypeError):
                continue

            # Try to detect project from bubble if not found from composer
            if not project:
                project = _detect_project_from_bubble(bdata)

            bubble_files = _extract_files_from_bubble(bdata)

            if bubble_type == 1:  # User message
                text = bdata.get("text", "")
                if not text or not text.strip():
                    continue
                messages.append({
                    "role": "user",
                    "content": text.strip(),
                    "model": None,
                    "project": project,
                    "timestamp": timestamp,
                    "files_referenced": bubble_files,
                    "tool_calls": [],
                    "session_id": f"composer:{conv_id}",
                    "conversation_id": conv_id,
                    "session_start": session_start,
                    "session_end": session_end,
                })

            elif bubble_type == 2:  # Assistant message
                text = bdata.get("text", "")
                model = _extract_model_from_bubble(bdata)

                # For assistant, also collect tool info from toolFormerData
                tool_calls = []
                tfd = bdata.get("toolFormerData", {})
                if isinstance(tfd, dict) and tfd.get("name"):
                    tool_calls.append(tfd["name"])

                if not text or not text.strip():
                    # Some assistant bubbles are pure tool calls with no text
                    if not tool_calls:
                        continue
                    text = f"[Tool: {', '.join(tool_calls)}]"

                messages.append({
                    "role": "assistant",
                    "content": text.strip(),
                    "model": model,
                    "project": project,
                    "timestamp": timestamp,
                    "files_referenced": bubble_files,
                    "tool_calls": tool_calls,
                    "session_id": f"composer:{conv_id}",
                    "conversation_id": conv_id,
                    "session_start": session_start,
                    "session_end": session_end,
                })

    return messages


def _detect_project_from_composer(comp_data: dict) -> Optional[str]:
    """Extract project name from composerData context fields."""
    ctx = comp_data.get("context", {})

    # Check fileSelections
    for sel in ctx.get("fileSelections", []):
        uri = sel.get("uri", {})
        fspath = uri.get("fsPath", "")
        if fspath:
            proj = extract_project_from_path(fspath)
            if proj:
                return proj

    # Check folderSelections
    for sel in ctx.get("folderSelections", []):
        uri = sel.get("uri", {})
        fspath = uri.get("fsPath", "")
        if fspath:
            proj = extract_project_from_path(fspath)
            if proj:
                return proj

    return None


def _resolve_uri_to_path(uri_data) -> Optional[str]:
    """Resolve various URI/path formats to a plain file path string."""
    if isinstance(uri_data, str):
        return uri_data if len(uri_data) > 3 else None
    if not isinstance(uri_data, dict):
        return None
    for key in ("fsPath", "path", "external"):
        val = uri_data.get(key, "")
        if isinstance(val, dict):
            val = val.get("fsPath", "")
        if isinstance(val, str) and len(val) > 3:
            return val
    return None


def _extract_files_from_bubble(bdata: dict) -> list[str]:
    """Extract all file paths referenced in a bubble's metadata fields.

    Collects paths from attachedFileCodeChunksUris, relevantFiles,
    diffsSinceLastApply, context.fileSelections, and toolFormerData args.
    """
    files = []

    for u in bdata.get("attachedFileCodeChunksUris", []):
        path = _resolve_uri_to_path(u)
        if path:
            files.append(path)

    for rf in bdata.get("relevantFiles", []):
        path = _resolve_uri_to_path(rf)
        if path:
            files.append(path)

    for diff in bdata.get("diffsSinceLastApply", []):
        path = _resolve_uri_to_path(diff)
        if path:
            files.append(path)

    ctx = bdata.get("context", {})
    for sel in ctx.get("fileSelections", []):
        path = _resolve_uri_to_path(sel.get("uri", {}))
        if path:
            files.append(path)

    tfd = bdata.get("toolFormerData", {})
    if isinstance(tfd, dict):
        args = tfd.get("args", {})
        if isinstance(args, dict):
            for key in ("path", "file", "filePath", "target_file"):
                val = args.get(key)
                if val and isinstance(val, str) and len(val) > 3:
                    files.append(val)

    return files


def _detect_project_from_bubble(bdata: dict) -> Optional[str]:
    """Extract project name from a bubble's file reference fields."""
    for filepath in _extract_files_from_bubble(bdata):
        proj = extract_project_from_path(filepath)
        if proj:
            return proj
    return None


def _extract_model_from_bubble(bdata: dict) -> Optional[str]:
    """Try to extract the model name from a bubble."""
    for tb in bdata.get("allThinkingBlocks", []):
        if isinstance(tb, dict):
            model = tb.get("modelName")
            if model:
                return model
    return None


# ---------------------------------------------------------------------------
# FALLBACK EXTRACTION: agentKv:blob (older format)
# ---------------------------------------------------------------------------

_SENTENCE_WORDS = frozenset({
    "write", "create", "the", "add", "fix", "update",
    "remove", "change", "make", "implement",
})


def _is_valid_workspace_path(path: str) -> bool:
    """Validate that extracted path looks like a real filesystem path."""
    if not path or len(path) > 300:
        return False
    if "\n" in path or "\r" in path or "`" in path:
        return False
    if "/" not in path and "\\" not in path and ":" not in path:
        return False
    lower = path.lower().strip()
    words = set(re.findall(r"\b[a-z]+\b", lower))
    if words & _SENTENCE_WORDS and "/" not in path[:20] and "\\" not in path[:20]:
        return False
    return True


def _extract_workspace_and_date(content) -> tuple[Optional[str], Optional[str]]:
    """Extract workspace/project path and Today's date from user message content."""
    result = {"workspace_path": None, "today_date": None}

    def search_in_text(text):
        if not isinstance(text, str):
            return
        m = re.search(r"Workspace Path:\s*([^\r\n]+)", text)
        if m:
            path = m.group(1).strip()
            if "%3A" in path or "%3a" in path:
                path = unquote(path)
            if re.match(r"^/[a-zA-Z]:", path):
                path = path[1:]
            if _is_valid_workspace_path(path):
                result["workspace_path"] = path
        if not result["workspace_path"]:
            m = re.search(r"[a-zA-Z]:\\Users\\[^\\]+\\[^\\]+\\[^\\]+\\([^\\]+)", text)
            if m:
                full = text[m.start():m.end()]
                if _is_valid_workspace_path(full):
                    result["workspace_path"] = full
        m = re.search(r"Today's date:\s*([A-Za-z]+\s+[A-Za-z]+\s+\d{1,2},\s+\d{4})", text)
        if m:
            result["today_date"] = m.group(1).strip()

    if isinstance(content, str):
        search_in_text(content)
    elif isinstance(content, list):
        for block in content:
            if isinstance(block, str):
                search_in_text(block)
            elif isinstance(block, dict):
                search_in_text(block.get("text", ""))
    return result["workspace_path"], result["today_date"]


def _parse_timestamp(date_str: Optional[str]) -> Optional[str]:
    if not date_str:
        return None
    try:
        dt = datetime.strptime(date_str.strip(), "%A %b %d, %Y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return None


def _extract_user_query(content) -> Optional[str]:
    """Extract the actual user query from agentKv content."""
    if isinstance(content, str):
        match = re.search(r"<user_query>\s*(.*?)\s*</user_query>", content, re.DOTALL)
        if match:
            return match.group(1).strip()
        if not content.startswith("<") and not content.startswith("{"):
            return content.strip()
        return None
    if not isinstance(content, list):
        return None
    for block in content:
        if isinstance(block, str):
            match = re.search(r"<user_query>\s*(.*?)\s*</user_query>", block, re.DOTALL)
            if match:
                return match.group(1).strip()
        elif isinstance(block, dict) and block.get("type") == "text":
            text = block.get("text", "")
            match = re.search(r"<user_query>\s*(.*?)\s*</user_query>", text, re.DOTALL)
            if match:
                return match.group(1).strip()
            if not text.startswith("<") and not text.startswith("{"):
                return text.strip()
    return None


def _extract_assistant_text(content) -> tuple[Optional[str], Optional[str], list[str], list[str]]:
    """Extract text, model, file refs, and tool calls from assistant content."""
    texts = []
    model = None

    if isinstance(content, str):
        return content.strip() if content.strip() else None, None, [], []
    if not isinstance(content, list):
        return None, None, [], []

    file_refs = []
    tool_calls = []

    for block in content:
        if isinstance(block, str):
            if block.strip():
                texts.append(block.strip())
            continue
        if not isinstance(block, dict):
            continue
        block_type = block.get("type", "")
        if block_type == "reasoning":
            provider_opts = block.get("providerOptions", {})
            cursor_opts = provider_opts.get("cursor", {})
            if "modelName" in cursor_opts:
                model = cursor_opts["modelName"]
            continue
        if block_type == "tool-call":
            tool_name = block.get("toolName", "unknown")
            tool_calls.append(tool_name)
            args = block.get("args", {})
            if isinstance(args, dict):
                for key in ("path", "file", "filePath", "target_file"):
                    if key in args:
                        file_refs.append(args[key])
            continue
        if block_type == "tool-result":
            continue
        if block_type == "text":
            text = block.get("text", "").strip()
            if text:
                texts.append(text)

    combined = "\n\n".join(texts) if texts else None
    return combined, model, file_refs, tool_calls


def _extract_from_agent_kv(conn: sqlite3.Connection) -> list[dict]:
    """Fallback: extract from agentKv:blob format (older Cursor versions).

    Each agentKv blob is a standalone message with its own key/session_id.
    For user messages, the project is detected from the embedded Workspace Path.
    For assistant messages, the project is detected from file paths in tool-call
    args — NOT inherited from a prior user message (which may be from a
    completely different conversation).
    """
    cursor = conn.cursor()

    cursor.execute("""
        SELECT key, value
        FROM cursorDiskKV
        WHERE key LIKE 'agentKv:blob:%'
        AND (value LIKE '%"role":"user"%' OR value LIKE '%"role":"assistant"%')
    """)

    messages = []

    for row in cursor.fetchall():
        try:
            raw = row[1]
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8", errors="replace")
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue

        role = data.get("role")
        content = data.get("content", [])
        key = row[0]

        if role == "system":
            continue

        if role == "user":
            workspace, date_str = _extract_workspace_and_date(content)
            timestamp = _parse_timestamp(date_str)
            project = extract_project_from_path(workspace) if workspace else None

            text = _extract_user_query(content)
            if not text:
                continue

            messages.append({
                "role": "user",
                "content": text,
                "model": None,
                "project": project,
                "timestamp": timestamp,
                "files_referenced": [],
                "tool_calls": [],
                "session_id": f"agentKv:{key}",
                "conversation_id": None,
            })

        elif role == "assistant":
            text, model, file_refs, tool_calls = _extract_assistant_text(content)
            if not text:
                continue

            # Detect project from this message's own file references
            project = None
            for ref in file_refs:
                project = extract_project_from_path(ref)
                if project:
                    break

            messages.append({
                "role": "assistant",
                "content": text,
                "model": model,
                "project": project,
                "timestamp": None,
                "files_referenced": file_refs,
                "tool_calls": tool_calls,
                "session_id": f"agentKv:{key}",
                "conversation_id": None,
            })

    return messages


# ---------------------------------------------------------------------------
# PUBLIC API
# ---------------------------------------------------------------------------

def extract_conversations_from_db(db_path: str) -> list[dict]:
    """Extract all conversation messages from Cursor's state database.

    Combines two extraction strategies for maximum coverage:
    1. composerData + bubbleId (current Cursor format)
    2. agentKv:blob (older format, catches conversations not in composer format)
    """
    conn = sqlite3.connect(db_path)

    # Primary: composerData + bubbleId
    composer_msgs = _extract_from_composer_data(conn)

    # Fallback: agentKv (older format)
    agent_msgs = _extract_from_agent_kv(conn)

    conn.close()

    # Merge: composer messages are authoritative; add agent messages
    # that don't overlap (identified by not having a conversation_id
    # that matches any composer conversation)
    composer_conv_ids = {m["conversation_id"] for m in composer_msgs if m.get("conversation_id")}

    all_messages = list(composer_msgs)
    for m in agent_msgs:
        # agentKv messages don't have conversation_id, so we always include them
        # (they cover different conversations than composerData)
        all_messages.append(m)

    # Assign "unknown" to messages without a project
    for m in all_messages:
        if not m.get("project"):
            m["project"] = "unknown"

    # Sort by timestamp then session_id
    def sort_key(m):
        ts = m.get("timestamp") or "9999-99-99"
        return (ts, m.get("session_id", ""))
    all_messages.sort(key=sort_key)

    # Build final schema
    result = []
    for m in all_messages:
        msg = {
            "role": m["role"],
            "content": m["content"],
            "model": m.get("model"),
            "project": m["project"],
            "timestamp": m.get("timestamp"),
            "files_referenced": m.get("files_referenced", []),
            "tool_calls": m.get("tool_calls", []),
            "session_id": m.get("session_id"),
        }
        if m.get("session_start"):
            msg["session_start"] = m["session_start"]
        if m.get("session_end"):
            msg["session_end"] = m["session_end"]
        result.append(msg)
    return result


def extract_conversations(db_path: Optional[str] = None) -> list[dict]:
    """Main entry point: extract conversations from Cursor's state database."""
    if db_path is None:
        db_path = str(get_cursor_db_path())
    if not Path(db_path).exists():
        return []
    return extract_conversations_from_db(db_path)


def group_by_project(messages: list[dict]) -> dict[str, list[dict]]:
    """Group messages by project name."""
    projects = defaultdict(list)
    for msg in messages:
        project = msg.get("project") or "unknown"
        projects[project].append(msg)
    return dict(projects)


def get_stats(messages: list[dict]) -> dict:
    """Calculate statistics about the conversation."""
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
    }
