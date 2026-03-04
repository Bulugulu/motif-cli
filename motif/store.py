"""Unified conversation store — reads/writes extracted data from ~/.motif/conversations/."""

import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict

from motif.config import get_conversations_dir


def save_conversations(messages: list[dict], source: str) -> dict[str, Path]:
    """Save extracted messages grouped by project.

    Returns a dict of project_name -> file_path for each project saved.
    """
    out_dir = get_conversations_dir(source)

    projects: dict[str, list[dict]] = defaultdict(list)
    for msg in messages:
        project = msg.get("project") or "unknown"
        projects[project].append(msg)

    saved = {}
    for project_name, project_msgs in projects.items():
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in project_name)
        file_path = out_dir / f"{safe_name}.json"

        data = {
            "source": source,
            "project": project_name,
            "extracted_at": datetime.now().isoformat(),
            "message_count": len(project_msgs),
            "messages": project_msgs,
        }

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        saved[project_name] = file_path

    return saved


def load_all_conversations() -> list[dict]:
    """Load all saved conversations from all sources."""
    base = get_conversations_dir()
    all_messages = []

    for json_file in base.rglob("*.json"):
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            messages = data.get("messages", [])
            all_messages.extend(messages)
        except (json.JSONDecodeError, OSError):
            continue

    return all_messages


def load_project_conversations(project: str) -> list[dict]:
    """Load conversations for a specific project across all sources."""
    all_msgs = load_all_conversations()
    project_lower = project.lower().strip()
    return [m for m in all_msgs if (m.get("project") or "unknown").lower() == project_lower]


def list_projects() -> list[dict]:
    """List all projects with message counts and sources.

    Returns list of dicts with: project, source, message_count, user_count,
    date_range, file_path, normalized_name, merge_group
    """
    from motif.analysis.pipeline import normalize_project_name

    base = get_conversations_dir()
    projects = []

    for json_file in base.rglob("*.json"):
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            messages = data.get("messages", [])
            user_msgs = [m for m in messages if m.get("role") == "user"]
            timestamps = sorted(m.get("timestamp") for m in messages if m.get("timestamp"))
            date_range = f"{timestamps[0]} to {timestamps[-1]}" if timestamps else "unknown"

            project_name = data.get("project", "unknown")
            normalized = normalize_project_name(project_name.lower())

            projects.append({
                "project": project_name,
                "source": data.get("source", "unknown"),
                "message_count": len(messages),
                "user_count": len(user_msgs),
                "date_range": date_range,
                "file_path": str(json_file),
                "normalized_name": normalized,
            })
        except (json.JSONDecodeError, OSError):
            continue

    projects.sort(key=lambda p: -p["message_count"])

    # Detect merge groups: projects with same normalized name
    norm_groups: dict[str, list[str]] = defaultdict(list)
    for p in projects:
        norm_groups[p["normalized_name"]].append(p["project"])

    for p in projects:
        group = norm_groups[p["normalized_name"]]
        p["merge_group"] = group if len(group) > 1 else None

    return projects
