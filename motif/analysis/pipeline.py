"""
Data preparation pipeline for Motif CLI analyze --prepare.

Takes raw extracted messages and prepares them for LLM analysis.
Output is a markdown file with structured data + analysis prompt.
"""

import re
from collections import OrderedDict

from motif.analysis.prompts import get_analysis_prompt, get_vibe_report_prompt

TRUNCATE_MARKER = "[...truncated]"
USER_LIMIT_DEFAULT = 1500
ASSISTANT_LIMIT_DEFAULT = 300
MAX_LINES = 5000
MAX_CHARS = 50000
TOKEN_ESTIMATE_CHARS = 4
BUDGET_DEFAULT = 60000
BUDGET_VIBE_REPORT = 200000
BATCH_TOKEN_LIMIT = 20000
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
      c-dev-journey-map-makers ΓåÆ journey-map-makers
      c_dev_journey_map_makers ΓåÆ journey-map-makers
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


# Regex for XML-style system tags injected by agent platforms
_NOISE_TAGS = (
    r'system_reminder|command-name|command-message|local-command-caveat'
    r'|tool_use|tool_result|antml_invoke|antml_parameter|think'
    r'|attached_files|open_and_recently_viewed_files'
    r'|code_selection|task_notification'
)
_SYSTEM_TAG_RE = re.compile(
    rf'<(?:{_NOISE_TAGS})[\s>].*?</(?:{_NOISE_TAGS})>',
    re.DOTALL,
)
_SELF_CLOSING_TAG_RE = re.compile(
    rf'<(?:{_NOISE_TAGS})[^>]*/\s*>',
)
_TOOL_LINE_RE = re.compile(r'^\[Tool:.*\]\s*$', re.MULTILINE)

REPEATED_MSG_MIN_LEN = 500
REPEATED_MSG_MIN_COUNT = 3
EMPTY_ASSISTANT_MIN_LEN = 50


def strip_system_noise(messages: list[dict]) -> list[dict]:
    """Strip XML-style system/tool metadata tags and other noise from messages.

    Targets tags like <system_reminder>, <think>, <command-message>, etc.,
    [Tool: ...] lines, repeated large user messages (e.g. SKILL.md loaded
    each session), and empty assistant stubs left after stripping.
    """
    # Pass 1: strip tags and tool lines
    cleaned_msgs = []
    for m in messages:
        content = _get_message_text(m)
        if not content:
            cleaned_msgs.append(m)
            continue
        cleaned = _SYSTEM_TAG_RE.sub("", content)
        cleaned = _SELF_CLOSING_TAG_RE.sub("", cleaned)
        cleaned = _TOOL_LINE_RE.sub("", cleaned)
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned).strip()
        if cleaned:
            cleaned_msgs.append({**m, "content": cleaned})
        else:
            cleaned_msgs.append(m)

    # Pass 2: deduplicate repeated large user messages (e.g. SKILL.md loads)
    user_text_counts: dict[str, int] = {}
    for m in cleaned_msgs:
        if m.get("role") == "user":
            text = _get_message_text(m)
            if len(text) >= REPEATED_MSG_MIN_LEN:
                key = text[:REPEATED_MSG_MIN_LEN].strip().lower()
                user_text_counts[key] = user_text_counts.get(key, 0) + 1

    repeated_keys = {k for k, v in user_text_counts.items() if v >= REPEATED_MSG_MIN_COUNT}
    seen_repeated: dict[str, int] = {}
    deduped = []
    for m in cleaned_msgs:
        if m.get("role") == "user":
            text = _get_message_text(m)
            if len(text) >= REPEATED_MSG_MIN_LEN:
                key = text[:REPEATED_MSG_MIN_LEN].strip().lower()
                if key in repeated_keys:
                    seen_repeated[key] = seen_repeated.get(key, 0) + 1
                    if seen_repeated[key] > 1:
                        total = user_text_counts[key]
                        stub = f"[Repeated content — seen {total} times, shown once above]"
                        deduped.append({**m, "content": stub})
                        continue
        deduped.append(m)

    # Pass 3: drop empty assistant stubs
    result = []
    for m in deduped:
        if m.get("role") != "user":
            text = _get_message_text(m).strip()
            if len(text) < EMPTY_ASSISTANT_MIN_LEN:
                continue
        result.append(m)

    return result


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


def _find_existing_claude_md() -> str | None:
    """Look for an existing CLAUDE.md in common locations relative to cwd.

    Checks cwd, then one level up, then two levels up. Returns file content
    if found, None otherwise. Truncates to 4000 chars to stay within budget.
    """
    from pathlib import Path
    cwd = Path.cwd()
    for candidate in [cwd, cwd.parent, cwd.parent.parent]:
        claude_path = candidate / "CLAUDE.md"
        if claude_path.is_file():
            try:
                content = claude_path.read_text(encoding="utf-8")
                if len(content) > 4000:
                    content = content[:4000] + "\n\n[...truncated at 4000 chars]"
                return content
            except OSError:
                continue
    return None


def _format_conversation_block(messages: list[dict]) -> list[str]:
    """Format conversation messages grouped by session_id."""
    lines = []
    current_session = None
    for m in messages:
        session_id = m.get("session_id")
        if session_id and session_id != current_session:
            current_session = session_id
            short_id = session_id.split(":")[-1][:20] if ":" in session_id else str(session_id)[:20]
            lines.append(f"### Session {short_id}")
            lines.append("")

        role = m.get("role", "user").upper()
        content = _get_message_text(m)
        lines.append(f"**[{role}]** {content}")
        lines.append("")
    return lines


def format_prepared_output(
    messages: list[dict],
    project: str,
    total_raw_count: int,
    pipeline_stats: dict,
    existing_claude_md: str | None = None,
    mode: str = "full",
) -> str:
    """Return a markdown string with conversation data and analysis instructions.

    Layout varies by mode:
      - "full": instructions at bottom, includes existing CLAUDE.md section
      - "vibe-report": instructions at top (so agents always see them first),
        skips existing CLAUDE.md (not relevant to vibe reports)
    """
    lines = []

    # Date range from messages
    timestamps = [m.get("timestamp") for m in messages if m.get("timestamp")]
    date_range = "\u2014"
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

    if mode == "vibe-report":
        # Instructions FIRST so agents that chunk-read always see them
        lines.append(get_vibe_report_prompt())
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## Conversation")
        lines.append("")
        lines.extend(_format_conversation_block(messages))
    else:
        # Full mode: existing CLAUDE.md, then conversation, then instructions at bottom
        if existing_claude_md:
            lines.append("---")
            lines.append("")
            lines.append("## Existing CLAUDE.md")
            lines.append("")
            lines.append("The user already has a CLAUDE.md with the following content. **Do not suggest rules or skills that duplicate what is already here.** Only suggest additions or refinements.")
            lines.append("")
            lines.append("```markdown")
            lines.append(existing_claude_md)
            lines.append("```")
            lines.append("")

        lines.append("---")
        lines.append("")
        lines.append("## Conversation")
        lines.append("")
        lines.extend(_format_conversation_block(messages))

    # Pipeline statistics
    lines.append("---")
    lines.append("")
    lines.append("## Pipeline Statistics")
    lines.append("")
    for key, val in pipeline_stats.items():
        lines.append(f"- **{key}:** {val}")
    lines.append("")

    # Full mode: analysis prompt at bottom
    if mode != "vibe-report":
        lines.append(get_analysis_prompt())

    return "\n".join(lines)


def _split_into_batches(
    messages: list[dict],
    batch_token_limit: int = BATCH_TOKEN_LIMIT,
) -> list[list[dict]]:
    """Split messages into batches grouped by session, each under batch_token_limit tokens.

    Sessions are kept intact — a session is never split across batches.
    """
    sessions = _group_by_session(messages)
    batches: list[list[dict]] = []
    current_batch: list[dict] = []
    current_tokens = 0

    for _sid, session_msgs in sessions.items():
        session_tokens = sum(
            len(_get_message_text(m)) for m in session_msgs
        ) // TOKEN_ESTIMATE_CHARS

        if current_batch and (current_tokens + session_tokens) > batch_token_limit:
            batches.append(current_batch)
            current_batch = []
            current_tokens = 0

        current_batch.extend(session_msgs)
        current_tokens += session_tokens

    if current_batch:
        batches.append(current_batch)

    return batches


def format_prepared_output_split(
    messages: list[dict],
    project: str,
    total_raw_count: int,
    pipeline_stats: dict,
) -> list[tuple[str, str]]:
    """Split vibe-report output into an instructions file + N batch data files.

    Returns a list of (filename_suffix, content) tuples:
      [("instructions", instr_md), ("batch-1", batch1_md), ("batch-2", batch2_md), ...]
    """
    batches = _split_into_batches(messages)
    sessions_all = _group_by_session(messages)

    timestamps = [m.get("timestamp") for m in messages if m.get("timestamp")]
    date_range = "\u2014"
    if timestamps:
        sorted_ts = sorted(timestamps)
        date_range = f"{sorted_ts[0]} to {sorted_ts[-1]}"

    # --- Build instructions file ---
    instr = []
    instr.append(f"# Motif Analysis: {project}")
    instr.append("")
    instr.append(f"**Date range:** {date_range}")
    instr.append(f"**Raw messages (all projects):** {total_raw_count}")
    instr.append(f"**Filtered messages:** {len(messages)}")
    instr.append(f"**Data files:** {len(batches)} batch(es)")
    instr.append("")

    instr.append(get_vibe_report_prompt())
    instr.append("")

    # Session index: which batch contains which sessions
    instr.append("---")
    instr.append("")
    instr.append("## Session Index")
    instr.append("")
    batch_session_map: dict[int, list[str]] = {}
    session_list = list(sessions_all.keys())
    msg_idx = 0
    for batch_num, batch_msgs in enumerate(batches, 1):
        batch_sids = []
        batch_sessions = _group_by_session(batch_msgs)
        for sid in batch_sessions:
            batch_sids.append(sid)
        batch_session_map[batch_num] = batch_sids
        for sid in batch_sids:
            short_id = sid.split(":")[-1][:20] if ":" in sid else str(sid)[:20]
            msg_count = len(sessions_all[sid])
            ts = sessions_all[sid][0].get("timestamp", "?")
            instr.append(f"- **{short_id}** ({ts}, {msg_count} msgs) — batch-{batch_num}")
    instr.append("")

    # Synthesis instructions
    instr.append("---")
    instr.append("")
    instr.append("## Synthesis Instructions")
    instr.append("")
    instr.append(f"There are **{len(batches)} data batch file(s)** to read.")
    instr.append("Each batch contains conversation sessions formatted as `### Session <id>` blocks.")
    instr.append("")
    instr.append("**For each batch**, extract these observations:")
    instr.append("- Notable quotes (funny, revealing, or showing personality)")
    instr.append("- Archetype signals (how the user approaches AI collaboration)")
    instr.append("- Superpower evidence (distinctive strengths)")
    instr.append("- Blind spot evidence (recurring weaknesses)")
    instr.append("- Questioning behavior examples (with type classification)")
    instr.append("- Communication style patterns")
    instr.append("- Problem articulation examples (weakest and strongest)")
    instr.append("- Domain expertise indicators")
    instr.append("- Critical thinking evidence")
    instr.append("- Vibe coding level indicators")
    instr.append("")
    instr.append("After reading all batches, **synthesize** the observations into the final JSON following the schema above.")
    instr.append("")

    # Pipeline statistics
    instr.append("---")
    instr.append("")
    instr.append("## Pipeline Statistics")
    instr.append("")
    for key, val in pipeline_stats.items():
        instr.append(f"- **{key}:** {val}")
    instr.append("")

    files = [("instructions", "\n".join(instr))]

    # --- Build batch files ---
    for batch_num, batch_msgs in enumerate(batches, 1):
        batch_sessions = _group_by_session(batch_msgs)
        batch_lines = []
        batch_lines.append(f"# Batch {batch_num} of {len(batches)}")
        batch_lines.append("")
        batch_lines.append(f"**Sessions:** {len(batch_sessions)} | **Messages:** {len(batch_msgs)}")
        batch_lines.append("")
        batch_lines.append("---")
        batch_lines.append("")
        batch_lines.extend(_format_conversation_block(batch_msgs))
        files.append((f"batch-{batch_num}", "\n".join(batch_lines)))

    return files


def prepare_analysis(
    messages: list[dict],
    project: str,
    budget: int | None = None,
    skip_relevance_filter: bool = False,
    mode: str = "full",
) -> tuple[str | list[tuple[str, str]], dict]:
    """Run the full pipeline and return formatted output + stats.

    Stages: scope -> relevance filter -> prepare -> noise filter
            -> [system noise strip for vibe-report] -> budget -> format.

    mode="full" (default): Personalize AI flow with full analysis prompt.
        Returns (single_string, stats).
    mode="vibe-report": Qualitative vibe report flow — strips system noise,
        splits output into instructions + batch files.
        Returns (list_of_(suffix, content)_tuples, stats).
    """
    effective_budget = budget if budget is not None else (
        BUDGET_VIBE_REPORT if mode == "vibe-report" else BUDGET_DEFAULT
    )
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

    # Stage 4b: Strip system/tool metadata for vibe-report mode
    noise_stripped_count = 0
    if mode == "vibe-report":
        before_strip = sum(len(_get_message_text(m)) for m in filtered)
        filtered = strip_system_noise(filtered)
        after_strip = sum(len(_get_message_text(m)) for m in filtered)
        noise_stripped_count = (before_strip - after_strip) // TOKEN_ESTIMATE_CHARS

    # Stage 5: Token budget
    final = apply_token_budget(filtered, effective_budget)
    final_count = len(final)

    estimated_tokens = sum(len(_get_message_text(m)) for m in final) // TOKEN_ESTIMATE_CHARS
    tokens_after_prepare = sum(len(_get_message_text(m)) for m in prepared) // TOKEN_ESTIMATE_CHARS
    tokens_after_filter = sum(len(_get_message_text(m)) for m in filtered) // TOKEN_ESTIMATE_CHARS
    budget_applied = filtered_count != final_count

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
        "budget": effective_budget,
        "mode": mode,
    }

    if mode == "vibe-report":
        pipeline_stats["system_noise_stripped_tokens"] = noise_stripped_count
        output = format_prepared_output_split(
            final, project, total_raw, pipeline_stats,
        )
        return output, pipeline_stats

    existing_claude_md = _find_existing_claude_md()
    if existing_claude_md:
        pipeline_stats["existing_claude_md"] = True

    output = format_prepared_output(
        final, project, total_raw, pipeline_stats,
        existing_claude_md=existing_claude_md,
        mode=mode,
    )

    return output, pipeline_stats
