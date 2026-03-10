"""
Data preparation pipeline for Motif CLI analyze --prepare.

Takes raw extracted messages and prepares them for LLM analysis.
Output is a markdown file with structured data + analysis prompt.
"""

import re
from collections import OrderedDict

from motif.analysis.prompts import get_analysis_prompt

TRUNCATE_MARKER = "[...truncated]"
USER_LIMIT_DEFAULT = 1500
ASSISTANT_LIMIT_DEFAULT = 300
MAX_LINES = 5000
MAX_CHARS = 50000
TOKEN_ESTIMATE_CHARS = 4
BUDGET_DEFAULT = 60000
TIGHT_USER_LIMIT = 1000
TIGHT_ASSISTANT_LIMIT = 150
DEDUP_MIN_LENGTH = 5
STRATIFIED_FIRST_PCT = 0.10
STRATIFIED_LAST_PCT = 0.10

# Known parent dirs for project path normalization (mirrors cursor.py)
_PROJECT_PARENTS = frozenset({
    "github", "repos", "projects", "workspace", "workspaces",
    "dev", "code", "sites", "src",
})

# Regex for extracting file system paths from message content
_WINDOWS_PATH_RE = re.compile(r'[a-zA-Z]:[/\\](?:[^\s*?"<>|`\n,;]+)')
_UNIX_PATH_RE = re.compile(r'(?:^|(?<=[\s`"\'(\[]))/((?:[\w.\-]+/){2,}[\w.\-]+)', re.MULTILINE)


def _estimate_tokens(text: str) -> int:
    """Estimate token count as len(text) / 4."""
    return len(text) // TOKEN_ESTIMATE_CHARS


def _get_message_text(msg: dict) -> str:
    """Extract text content from a message dict."""
    return msg.get("content") or ""


def normalize_project_name(name: str) -> str:
    """Normalize a project name by stripping path-derived prefixes.

    Handles cases like:
      c-dev-journey-map-makers → journey-map-makers
      c_dev_journey_map_makers → journey-map-makers
    """
    if not name:
        return name

    # Split on common separators to detect path prefixes
    parts = re.split(r'[-_]', name.lower())

    # Drive letter + parent dir: c-dev-project or c_projects_foo
    if len(parts) >= 3 and len(parts[0]) == 1 and parts[0].isalpha():
        if parts[1] in _PROJECT_PARENTS:
            return "-".join(parts[2:])

    # Parent dir without drive letter: dev-project, projects-foo
    if len(parts) >= 2 and parts[0] in _PROJECT_PARENTS:
        return "-".join(parts[1:])

    return name.lower()


def scope_to_project(messages: list[dict], project: str) -> list[dict]:
    """Filter messages to a single project, with normalized name matching."""
    project_lower = project.lower().strip()
    project_normalized = normalize_project_name(project_lower)

    result = []
    for m in messages:
        msg_project = (m.get("project") or "unknown").lower()
        if msg_project == project_lower:
            result.append(m)
        elif normalize_project_name(msg_project) == project_normalized:
            result.append(m)
    return result


# ---------------------------------------------------------------------------
# Relevance filtering (file-path heuristic)
# ---------------------------------------------------------------------------

def _extract_paths_from_text(text: str) -> list[str]:
    """Extract plausible file system paths from message text."""
    if not text:
        return []
    paths = []
    for m in _WINDOWS_PATH_RE.finditer(text):
        p = m.group(0).rstrip(".,;:)]}'\"`")
        paths.append(p.replace("\\", "/"))
    for m in _UNIX_PATH_RE.finditer(text):
        p = m.group(0).rstrip(".,;:)]}'\"`")
        if len(p) > 5:
            paths.append(p)
    return paths


def _path_matches_project(path: str, project: str) -> bool:
    """Check if a file path contains the project name as a path segment."""
    normalized = path.replace("\\", "/").lower()
    proj_lower = project.lower()
    segments = [s for s in normalized.split("/") if s]
    return any(s == proj_lower for s in segments)


def _group_by_session(messages: list[dict]) -> OrderedDict:
    """Group messages by session_id, preserving insertion order."""
    groups: OrderedDict[str, list[dict]] = OrderedDict()
    for m in messages:
        sid = m.get("session_id") or "unknown"
        if sid not in groups:
            groups[sid] = []
        groups[sid].append(m)
    return groups


def score_session_relevance(
    session_id: str,
    session_messages: list[dict],
    project: str,
) -> dict:
    """Score a single session's relevance to the target project.

    Collects file paths from files_referenced and content parsing.
    Returns a dict with score, reason, and file path counts.
    """
    all_paths: list[str] = []

    for m in session_messages:
        for ref in m.get("files_referenced", []):
            if ref and isinstance(ref, str):
                all_paths.append(ref.replace("\\", "/").lower())
        if m.get("role") == "assistant":
            all_paths.extend(
                p.lower() for p in _extract_paths_from_text(m.get("content", ""))
            )

    unique_paths = list(set(p for p in all_paths if len(p) > 3))

    if not unique_paths:
        return {
            "session_id": session_id,
            "total_messages": len(session_messages),
            "paths_total": 0,
            "paths_in_project": 0,
            "score": None,
            "reason": "no_paths_detected",
            "keep": True,
        }

    matches = sum(1 for p in unique_paths if _path_matches_project(p, project))
    score = matches / len(unique_paths)

    if matches == 0:
        return {
            "session_id": session_id,
            "total_messages": len(session_messages),
            "paths_total": len(unique_paths),
            "paths_in_project": 0,
            "score": 0.0,
            "reason": "all_paths_outside_project",
            "keep": False,
        }

    return {
        "session_id": session_id,
        "total_messages": len(session_messages),
        "paths_total": len(unique_paths),
        "paths_in_project": matches,
        "score": round(score, 2),
        "reason": "relevant",
        "keep": True,
    }


def filter_misattributed(
    messages: list[dict],
    project: str,
) -> tuple[list[dict], dict]:
    """Filter out sessions whose file paths don't match the target project.

    Only removes sessions where file paths ARE present but NONE match.
    Sessions with no detectable file paths are kept (no evidence to filter).

    Returns (kept_messages, filter_stats).
    """
    sessions = _group_by_session(messages)
    kept: list[dict] = []
    removed_count = 0
    removed_msg_count = 0
    no_paths_count = 0
    session_scores: list[dict] = []

    for sid, session_msgs in sessions.items():
        result = score_session_relevance(sid, session_msgs, project)
        session_scores.append(result)

        if result["keep"]:
            kept.extend(session_msgs)
            if result["reason"] == "no_paths_detected":
                no_paths_count += 1
        else:
            removed_count += 1
            removed_msg_count += len(session_msgs)

    stats = {
        "sessions_total": len(sessions),
        "sessions_kept": len(sessions) - removed_count,
        "sessions_removed": removed_count,
        "messages_removed": removed_msg_count,
        "sessions_no_paths": no_paths_count,
        "session_scores": session_scores,
    }
    return kept, stats


def preview_relevance(
    messages: list[dict],
    project: str,
) -> list[dict]:
    """Score all sessions for relevance without filtering.

    Returns a list of session score dicts for display.
    """
    sessions = _group_by_session(messages)
    scores = []
    for sid, session_msgs in sessions.items():
        result = score_session_relevance(sid, session_msgs, project)
        # Add a content sample (first user message)
        sample = ""
        for m in session_msgs:
            if m.get("role") == "user":
                sample = (m.get("content") or "")[:200]
                break
        result["sample"] = sample
        result["timestamp"] = session_msgs[0].get("timestamp")
        scores.append(result)
    return scores


def prepare_messages(
    messages: list[dict],
    user_limit: int = USER_LIMIT_DEFAULT,
    assistant_limit: int = ASSISTANT_LIMIT_DEFAULT,
) -> list[dict]:
    """
    Keep all user messages (truncate to user_limit chars).
    Truncate assistant messages to assistant_limit chars (stub showing what agent did).
    """
    result = []
    for m in messages:
        content = _get_message_text(m)
        role = m.get("role", "user")

        if role == "user":
            if len(content) > user_limit:
                content = content[:user_limit] + TRUNCATE_MARKER
        else:
            if len(content) > assistant_limit:
                content = content[:assistant_limit] + TRUNCATE_MARKER

        result.append({**m, "content": content})
    return result


def filter_noise(
    messages: list[dict],
    max_lines: int = MAX_LINES,
    max_chars: int = MAX_CHARS,
) -> tuple[list[dict], dict]:
    """
    Drop messages with >max_lines lines (giant data artifacts).
    Drop messages with >max_chars chars (single-line minified blobs).
    Return (filtered_messages, stats_dict).
    """
    dropped_lines = 0
    dropped_chars = 0

    filtered = []
    for m in messages:
        content = _get_message_text(m)
        lines = content.count("\n") + 1

        if lines > max_lines:
            dropped_lines += 1
            continue
        if len(content) > max_chars:
            dropped_chars += 1
            continue

        filtered.append(m)

    stats = {
        "dropped_lines": dropped_lines,
        "dropped_chars": dropped_chars,
        "dropped_total": dropped_lines + dropped_chars,
    }
    return filtered, stats


def _truncate_message(msg: dict, user_limit: int, assistant_limit: int) -> dict:
    """Apply truncation limits to a single message."""
    content = _get_message_text(msg)
    role = msg.get("role", "user")

    if role == "user":
        if len(content) > user_limit:
            content = content[:user_limit] + TRUNCATE_MARKER
    else:
        if len(content) > assistant_limit:
            content = content[:assistant_limit] + TRUNCATE_MARKER

    return {**msg, "content": content}


def _messages_are_near_identical(a: str, b: str) -> bool:
    """Check if two short messages are near-identical (for deduplication)."""
    if len(a) < DEDUP_MIN_LENGTH or len(b) < DEDUP_MIN_LENGTH:
        return False
    a_norm = a.strip().lower()
    b_norm = b.strip().lower()
    if a_norm == b_norm:
        return True
    # One is prefix of the other (e.g. "commit" vs "commit and push")
    if a_norm in b_norm or b_norm in a_norm:
        return True
    return False


def _collapse_repeated_messages(messages: list[dict]) -> list[dict]:
    """
    Collapse consecutive near-identical short messages into [USER xN] or [ASSISTANT xN] stubs.
    """
    if not messages:
        return []

    result = []
    i = 0
    while i < len(messages):
        m = messages[i]
        content = _get_message_text(m)
        role = m.get("role", "user")

        # Look ahead for consecutive near-identical messages
        count = 1
        j = i + 1
        while j < len(messages) and messages[j].get("role") == role:
            next_content = _get_message_text(messages[j])
            if _messages_are_near_identical(content, next_content):
                count += 1
                j += 1
            else:
                break

        if count > 1 and len(content.strip()) < 100:
            # Collapse into stub
            stub = f"[{role.upper()} x{count}] {content.strip()}"
            result.append({**m, "content": stub})
            i = j
        else:
            result.append(m)
            i += 1

    return result


def _stratified_sample(messages: list[dict], target_count: int) -> list[dict]:
    """
    Keep first 10%, last 10%, sample middle to reach target_count.
    Preserves conversation order.
    """
    n = len(messages)
    if n <= target_count:
        return messages

    first_n = max(1, int(n * STRATIFIED_FIRST_PCT))
    last_n = max(1, int(n * STRATIFIED_LAST_PCT))
    middle_start = first_n
    middle_end = n - last_n

    if middle_start >= middle_end:
        return messages[:target_count]

    middle_slice = messages[middle_start:middle_end]
    middle_target = target_count - first_n - last_n

    if middle_target <= 0:
        return messages[:first_n] + messages[-last_n:]

    # Sample evenly from middle
    step = max(1, len(middle_slice) // middle_target)
    sampled_middle = [middle_slice[i] for i in range(0, len(middle_slice), step)][:middle_target]

    return messages[:first_n] + sampled_middle + messages[-last_n:]


def apply_token_budget(messages: list[dict], budget: int = BUDGET_DEFAULT) -> list[dict]:
    """
    Estimate tokens as len(text)/4.
    If under budget, return as-is.
    If over: tighten truncation (1000 user, 150 assistant), deduplicate near-identical messages,
    then stratified sample (first 10%, last 10%, sample middle).
    """
    total_chars = sum(len(_get_message_text(m)) for m in messages)
    estimated = total_chars // TOKEN_ESTIMATE_CHARS

    if estimated <= budget:
        return messages

    # Step 1: Tighten truncation
    tightened = []
    for m in messages:
        tightened.append(_truncate_message(m, TIGHT_USER_LIMIT, TIGHT_ASSISTANT_LIMIT))

    total_chars = sum(len(_get_message_text(m)) for m in tightened)
    estimated = total_chars // TOKEN_ESTIMATE_CHARS

    if estimated <= budget:
        return tightened

    # Step 2: Deduplicate near-identical messages
    deduped = _collapse_repeated_messages(tightened)
    total_chars = sum(len(_get_message_text(m)) for m in deduped)
    estimated = total_chars // TOKEN_ESTIMATE_CHARS

    if estimated <= budget:
        return deduped

    # Step 3: Stratified sample to fit budget
    # Target: budget tokens * 4 chars/token = budget * 4 chars
    target_chars = budget * TOKEN_ESTIMATE_CHARS
    # Approximate: we need ~target_chars / avg_msg_len messages
    avg_len = total_chars / len(deduped) if deduped else 1
    target_count = max(10, int(target_chars / avg_len))

    return _stratified_sample(deduped, min(target_count, len(deduped)))


def format_prepared_output(
    messages: list[dict],
    project: str,
    total_raw_count: int,
    pipeline_stats: dict,
) -> str:
    """
    Return a markdown string with:
    1. Header: project name, date range, message counts (raw vs filtered)
    2. Conversation turns grouped by session_id (### Session headers)
    3. Each message: **[USER]** or **[ASSISTANT]** + content
    4. Pipeline statistics section
    5. Analysis prompt appended
    """
    lines = []

    # Date range from messages
    timestamps = [m.get("timestamp") for m in messages if m.get("timestamp")]
    date_range = "—"
    if timestamps:
        sorted_ts = sorted(timestamps)
        date_range = f"{sorted_ts[0]} to {sorted_ts[-1]}"

    # Header
    lines.append(f"# Motif Analysis: {project}")
    lines.append("")
    lines.append(f"**Date range:** {date_range}")
    lines.append(f"**Raw messages (all projects):** {total_raw_count}")
    lines.append(f"**Filtered messages:** {len(messages)}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Conversation")
    lines.append("")

    # Group by session_id
    current_session = None
    for m in messages:
        session_id = m.get("session_id")
        if session_id and session_id != current_session:
            current_session = session_id
            # Use short session id for header (full key can be long)
            short_id = session_id.split(":")[-1][:20] if ":" in session_id else str(session_id)[:20]
            lines.append(f"### Session {short_id}")
            lines.append("")

        role = m.get("role", "user").upper()
        content = _get_message_text(m)
        lines.append(f"**[{role}]** {content}")
        lines.append("")

    # Pipeline statistics
    lines.append("---")
    lines.append("")
    lines.append("## Pipeline Statistics")
    lines.append("")
    for key, val in pipeline_stats.items():
        lines.append(f"- **{key}:** {val}")
    lines.append("")

    # Append analysis prompt
    lines.append(get_analysis_prompt())

    return "\n".join(lines)


def prepare_analysis(
    messages: list[dict],
    project: str,
    budget: int = BUDGET_DEFAULT,
    skip_relevance_filter: bool = False,
) -> tuple[str, dict]:
    """
    Run the full pipeline: scope -> relevance filter -> prepare -> noise filter -> budget -> format.
    Returns (formatted_output_string, pipeline_stats_dict).
    """
    total_raw = len(messages)

    # Stage 1: Scope to project (with normalized name matching)
    scoped = scope_to_project(messages, project)
    scoped_count = len(scoped)

    # Stage 2: Relevance filter (file-path heuristic)
    relevance_stats = {}
    if skip_relevance_filter:
        relevance_filtered = scoped
        relevance_stats = {"sessions_removed": 0, "messages_removed": 0, "skipped": True}
    else:
        relevance_filtered, relevance_stats = filter_misattributed(scoped, project)
    relevance_count = len(relevance_filtered)

    # Stage 3: Prepare (truncate)
    prepared = prepare_messages(relevance_filtered)

    # Stage 4: Filter noise
    filtered, noise_stats = filter_noise(prepared)
    filtered_count = len(filtered)

    # Stage 5: Token budget
    final = apply_token_budget(filtered, budget)
    final_count = len(final)

    estimated_tokens = sum(len(_get_message_text(m)) for m in final) // TOKEN_ESTIMATE_CHARS
    tokens_after_prepare = sum(len(_get_message_text(m)) for m in prepared) // TOKEN_ESTIMATE_CHARS
    tokens_after_filter = sum(len(_get_message_text(m)) for m in filtered) // TOKEN_ESTIMATE_CHARS
    budget_applied = filtered_count != final_count or estimated_tokens > budget

    pipeline_stats = {
        "raw_count": total_raw,
        "scoped_count": scoped_count,
        "relevance_count": relevance_count,
        "relevance_sessions_removed": relevance_stats.get("sessions_removed", 0),
        "relevance_messages_removed": relevance_stats.get("messages_removed", 0),
        "relevance_sessions_no_paths": relevance_stats.get("sessions_no_paths", 0),
        "filtered_count": filtered_count,
        "final_count": final_count,
        "estimated_tokens": estimated_tokens,
        "tokens_after_prepare": tokens_after_prepare,
        "tokens_after_filter": tokens_after_filter,
        "dropped_noise": noise_stats.get("dropped_total", 0),
        "budget_applied": budget_applied,
    }

    output = format_prepared_output(final, project, total_raw, pipeline_stats)

    return output, pipeline_stats
