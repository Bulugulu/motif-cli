"""
Claude Code Conversation Extractor

Extracts user/assistant dialogue from Claude Code's session files.
Organizes by project and includes file reference metrics.

Exports:
- get_claude_data_path() -> Path
- extract_conversations(claude_path: Optional[str] = None) -> list[dict]
- group_by_project(messages) -> dict[str, list[dict]]
- get_stats(messages) -> dict
"""

import json
from pathlib import Path
from typing import Optional
from datetime import datetime
from collections import defaultdict
import platform


def get_claude_data_path() -> Path:
    """Get the Claude Code data directory path for the current OS."""
    system = platform.system()
    home = Path.home()
    return home / ".claude"


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


def extract_text_from_content(content) -> Optional[str]:
    """Extract text content from message content (string or array)."""
    if isinstance(content, str):
        return content.strip() if content.strip() else None

    if not isinstance(content, list):
        return None

    texts = []
    for block in content:
        if isinstance(block, str):
            if block.strip():
                texts.append(block.strip())
            continue

        if not isinstance(block, dict):
            continue

        block_type = block.get("type", "")

        # Skip thinking/reasoning blocks
        if block_type == "thinking":
            continue

        # Skip tool calls and results
        if block_type in ("tool_use", "tool_result"):
            continue

        # Keep text blocks
        if block_type == "text":
            text = block.get("text", "").strip()
            if text:
                texts.append(text)

    return "\n\n".join(texts) if texts else None


def extract_file_references(content) -> list[str]:
    """Extract file paths from tool calls in content."""
    files = set()

    if not isinstance(content, list):
        return []

    for block in content:
        if not isinstance(block, dict):
            continue

        block_type = block.get("type", "")

        if block_type == "tool_use":
            input_data = block.get("input", {})

            # Common file path arguments
            for key in ["file_path", "path", "file", "filePath", "target_file"]:
                if key in input_data:
                    files.add(input_data[key])

            # Glob patterns
            if "pattern" in input_data:
                pattern = input_data["pattern"]
                if "/" in pattern:
                    files.add(pattern.rsplit("/", 1)[0] + "/...")

    return sorted(files)


def extract_tool_calls_summary(content) -> list[str]:
    """Extract summary of tool calls made."""
    tools = []

    if not isinstance(content, list):
        return []

    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "tool_use":
            tool_name = block.get("name", "unknown")
            tools.append(tool_name)

    return tools


def parse_session_file(file_path: Path) -> list[dict]:
    """Parse a single session JSONL file."""
    messages = []

    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue

            msg_type = data.get("type")

            if msg_type == "user":
                message = data.get("message", {})
                content = message.get("content", "")
                text = extract_text_from_content(content)

                if not text:
                    continue

                messages.append({
                    "role": "user",
                    "content": text,
                    "model": None,
                    "project": normalize_project_name(data.get("cwd")),
                    "timestamp": data.get("timestamp"),
                    "session_id": data.get("sessionId"),
                    "files_referenced": [],
                    "tool_calls": [],
                })

            elif msg_type == "assistant":
                message = data.get("message", {})
                content = message.get("content", [])
                text = extract_text_from_content(content)

                if not text:
                    continue

                file_refs = extract_file_references(content)
                tool_calls = extract_tool_calls_summary(content)

                messages.append({
                    "role": "assistant",
                    "content": text,
                    "model": message.get("model"),
                    "project": normalize_project_name(data.get("cwd")),
                    "timestamp": data.get("timestamp"),
                    "session_id": data.get("sessionId"),
                    "files_referenced": file_refs,
                    "tool_calls": tool_calls,
                })

    return messages


def find_all_session_files(claude_path: Path, include_subagents: bool = True) -> list[Path]:
    """Find all session JSONL files in Claude Code data directory."""
    session_files = []

    projects_dir = claude_path / "projects"
    if not projects_dir.exists():
        return session_files

    for jsonl_file in projects_dir.rglob("*.jsonl"):
        if not include_subagents and "subagents" in str(jsonl_file):
            continue
        session_files.append(jsonl_file)

    return session_files


def extract_all_conversations(claude_path: Path) -> list[dict]:
    """Extract all conversations from all session files."""
    all_messages = []

    session_files = find_all_session_files(claude_path)

    for session_file in session_files:
        try:
            messages = parse_session_file(session_file)
            all_messages.extend(messages)
        except Exception:
            continue

    def sort_key(m):
        ts = m.get("timestamp") or ""
        return ts

    all_messages.sort(key=sort_key)

    return all_messages


def extract_conversations(claude_path: Optional[str] = None) -> list[dict]:
    """
    Main entry point: extract conversations from Claude Code session files.
    Auto-detects data path if not provided.
    """
    if claude_path is None:
        path = get_claude_data_path()
    else:
        path = Path(claude_path)
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
