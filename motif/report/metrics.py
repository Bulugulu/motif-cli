"""
Quantitative metrics for the Vibe Report.

Computes all metrics from a list of message dicts loaded from ~/.motif/conversations/.
"""

import re
from collections import defaultdict
from datetime import datetime
from typing import Any


def _parse_ts(s: str | None) -> datetime | None:
    if not s or not isinstance(s, str):
        return None
    s = s.strip()
    if not s:
        return None
    s = re.sub(r"Z$", "", s)
    s = re.sub(r"[+-]\d{2}:?\d{2}(?::?\d{2})?$", "", s)
    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(s[:26], fmt)
        except (ValueError, TypeError):
            continue
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d")
    except (ValueError, TypeError):
        return None


def _date_str(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


def _week_str(dt: datetime) -> str:
    return dt.strftime("%Y-W%U")


SWEAR_WORDS = re.compile(
    r"\b(fuck|shit|damn|hell|crap|wtf|ffs|dammit|goddamn|bullshit)\b",
    re.IGNORECASE,
)

FRUSTRATION_PHRASES = [
    r"still broken",
    r"still not working",
    r"try again",
    r"just do it",
    r"just fix it",
    r"come on",
    r"seriously\?",
    r"that's wrong",
    r"you broke",
    r"it's broken",
    r"not what i asked",
    r"\bugh\b",
    r"\bargh\b",
    r"\bsigh\b",
]

CATCHPHRASES = [
    r"commit and push",
    r"refresh yourself",
    r"just do it",
    r"let's go",
    r"let's do",
    r"let's start",
    r"let's continue",
    r"ship it",
    r"it works",
    r"\bnice\b",
    r"\bperfect\b",
    r"\bawesome\b",
    r"we shall continue",
]

FRUSTRATION_PATTERNS = [re.compile(p, re.IGNORECASE) for p in FRUSTRATION_PHRASES]
CATCHPHRASE_PATTERNS = [re.compile(p, re.IGNORECASE) for p in CATCHPHRASES]


def _count_swears(text: str) -> int:
    return len(SWEAR_WORDS.findall(text))


def _count_frustration(text: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for pat in FRUSTRATION_PATTERNS:
        for m in pat.finditer(text):
            phrase = m.group(0).lower()
            counts[phrase] = counts.get(phrase, 0) + 1
    return counts


def _count_catchphrases(text: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for pat in CATCHPHRASE_PATTERNS:
        for m in pat.finditer(text):
            phrase = m.group(0).lower()
            counts[phrase] = counts.get(phrase, 0) + 1
    return counts


def _build_session_map(messages: list[dict]) -> dict[str, dict[str, Any]]:
    sessions: dict[str, dict[str, Any]] = {}
    for m in messages:
        sid = m.get("session_id")
        if not sid:
            continue
        if sid not in sessions:
            sessions[sid] = {
                "start": None,
                "end": None,
                "messages": [],
                "project": m.get("project") or "unknown",
            }
        s = sessions[sid]
        ts = _parse_ts(m.get("timestamp"))
        start = _parse_ts(m.get("session_start"))
        end = _parse_ts(m.get("session_end"))
        if start:
            if s["start"] is None or start < s["start"]:
                s["start"] = start
        if end:
            if s["end"] is None or end > s["end"]:
                s["end"] = end
        s["messages"].append(m)
    return sessions


def _sweep_peak(events: list[tuple[datetime, int]]) -> int:
    if not events:
        return 0
    events = sorted(events, key=lambda e: (e[0], e[1]))
    peak = 0
    curr = 0
    for _, delta in events:
        curr += delta
        peak = max(peak, curr)
    return peak


def _concurrency_metrics(sessions: dict[str, dict]) -> dict:
    valid = [
        s for s in sessions.values()
        if s["start"] is not None and s["end"] is not None
    ]
    if not valid:
        return {
            "peak_concurrent": 0,
            "peak_time": None,
            "avg_daily_peak": 0.0,
            "median_daily_peak": 0,
            "weekly_avg_peak": {},
            "distribution": {},
        }

    all_events: list[tuple[datetime, int]] = []
    for s in valid:
        all_events.append((s["start"], 1))
        all_events.append((s["end"], -1))

    all_events.sort(key=lambda e: (e[0], e[1]))
    peak_concurrent = 0
    peak_time: datetime | None = None
    curr = 0
    for t, delta in all_events:
        curr += delta
        if curr > peak_concurrent:
            peak_concurrent = curr
            peak_time = t

    min_date = min(s["start"] for s in valid)
    max_date = max(s["end"] for s in valid)
    dates = []
    d = min_date.date()
    end_d = max_date.date()
    while d <= end_d:
        dates.append(datetime.combine(d, datetime.min.time()))
        d = datetime.fromordinal(d.toordinal() + 1).date()

    daily_peaks: list[int] = []
    for day_start in dates:
        day_end = day_start.replace(hour=23, minute=59, second=59, microsecond=999999)
        day_events: list[tuple[datetime, int]] = []
        for s in valid:
            if s["start"] <= day_end and s["end"] >= day_start:
                start_in = max(s["start"], day_start)
                end_in = min(s["end"], day_end)
                day_events.append((start_in, 1))
                day_events.append((end_in, -1))
        daily_peaks.append(_sweep_peak(day_events))

    distribution: dict[int, int] = defaultdict(int)
    for p in daily_peaks:
        distribution[p] += 1

    weekly_peaks: dict[str, list[int]] = defaultdict(list)
    for day_start in dates:
        w = _week_str(day_start)
        day_end = day_start.replace(hour=23, minute=59, second=59, microsecond=999999)
        day_events = []
        for s in valid:
            if s["start"] <= day_end and s["end"] >= day_start:
                start_in = max(s["start"], day_start)
                end_in = min(s["end"], day_end)
                day_events.append((start_in, 1))
                day_events.append((end_in, -1))
        weekly_peaks[w].append(_sweep_peak(day_events))

    weekly_avg_peak = {
        w: sum(ps) / len(ps) if ps else 0.0
        for w, ps in weekly_peaks.items()
    }

    sorted_peaks = sorted(daily_peaks) if daily_peaks else [0]
    median_idx = len(sorted_peaks) // 2
    median_daily_peak = (
        sorted_peaks[median_idx]
        if len(sorted_peaks) % 2
        else (sorted_peaks[median_idx - 1] + sorted_peaks[median_idx]) // 2
    )

    return {
        "peak_concurrent": peak_concurrent,
        "peak_time": peak_time.isoformat() if peak_time else None,
        "avg_daily_peak": sum(daily_peaks) / len(daily_peaks) if daily_peaks else 0.0,
        "median_daily_peak": median_daily_peak,
        "weekly_avg_peak": weekly_avg_peak,
        "distribution": dict(distribution),
    }


def _growth_scorecard(
    sessions: dict[str, dict],
    messages: list[dict],
) -> dict:
    valid_sessions = [
        (sid, s) for sid, s in sessions.items()
        if s["messages"] and s["start"] is not None
    ]
    if len(valid_sessions) < 8:
        return {
            "avg_prompt_length": {"early": 0, "recent": 0, "change_pct": 0.0},
            "files_per_session": {"early": 0, "recent": 0, "change_pct": 0.0},
            "autonomy_ratio": {"early": 0.0, "recent": 0.0, "change_pct": 0.0},
            "msgs_per_session": {"early": 0, "recent": 0, "change_pct": 0.0},
            "tool_calls_per_session": {"early": 0, "recent": 0, "change_pct": 0.0},
            "output_density": {"early": 0, "recent": 0, "change_pct": 0.0},
        }

    sorted_sessions = sorted(
        valid_sessions,
        key=lambda x: x[1]["start"] or datetime.min,
    )
    n = len(sorted_sessions)
    early_count = max(1, n // 4)
    recent_count = max(1, n // 4)
    early_sids = {s[0] for s in sorted_sessions[:early_count]}
    recent_sids = {s[0] for s in sorted_sessions[-recent_count:]}

    def session_metrics(sids: set[str]) -> dict[str, Any]:
        msgs = [m for m in messages if m.get("session_id") in sids]
        user_msgs = [m for m in msgs if m.get("role") == "user"]
        assistant_msgs = [m for m in msgs if m.get("role") == "assistant"]
        tool_calls = sum(len(m.get("tool_calls") or []) for m in msgs)
        output_chars = sum(m.get("output_chars", 0) for m in msgs)
        sess_count = len(sids)
        total_user_len = sum(len(m.get("content") or "") for m in user_msgs)
        total_files = sum(len(m.get("files_referenced") or []) for m in msgs)
        return {
            "prompt_len": total_user_len / len(user_msgs) if user_msgs else 0,
            "files": total_files / sess_count if sess_count else 0,
            "autonomy": (len(assistant_msgs) + tool_calls) / len(user_msgs) if user_msgs else 0.0,
            "msgs": len(msgs) / sess_count if sess_count else 0,
            "tool_calls": tool_calls / sess_count if sess_count else 0,
            "output_density": output_chars / len(user_msgs) if user_msgs else 0,
        }

    early = session_metrics(early_sids)
    recent = session_metrics(recent_sids)

    def pct_change(a: float, b: float) -> float:
        if a == 0:
            return 100.0 if b > 0 else 0.0
        return ((b - a) / a) * 100

    return {
        "avg_prompt_length": {
            "early": round(early["prompt_len"]),
            "recent": round(recent["prompt_len"]),
            "change_pct": round(pct_change(early["prompt_len"], recent["prompt_len"]), 1),
        },
        "files_per_session": {
            "early": round(early["files"], 1),
            "recent": round(recent["files"], 1),
            "change_pct": round(pct_change(early["files"], recent["files"]), 1),
        },
        "autonomy_ratio": {
            "early": round(early["autonomy"], 2),
            "recent": round(recent["autonomy"], 2),
            "change_pct": round(pct_change(early["autonomy"], recent["autonomy"]), 1),
        },
        "msgs_per_session": {
            "early": round(early["msgs"], 1),
            "recent": round(recent["msgs"], 1),
            "change_pct": round(pct_change(early["msgs"], recent["msgs"]), 1),
        },
        "tool_calls_per_session": {
            "early": round(early["tool_calls"], 1),
            "recent": round(recent["tool_calls"], 1),
            "change_pct": round(pct_change(early["tool_calls"], recent["tool_calls"]), 1),
        },
        "output_density": {
            "early": round(early["output_density"]),
            "recent": round(recent["output_density"]),
            "change_pct": round(pct_change(early["output_density"], recent["output_density"]), 1),
        },
    }


def _personality_metrics(messages: list[dict], sessions: dict[str, dict]) -> dict:
    user_msgs = [m for m in messages if m.get("role") == "user"]
    total_content = " ".join(m.get("content") or "" for m in user_msgs)
    total_user_chars = sum(len(m.get("content") or "") for m in user_msgs)

    swear_count = _count_swears(total_content)

    session_swears: dict[str, int] = {}
    for m in user_msgs:
        sid = m.get("session_id")
        if sid:
            session_swears[sid] = session_swears.get(sid, 0) + _count_swears(m.get("content") or "")  # noqa: E501
    peak_session_swears = max(session_swears.values()) if session_swears else 0

    frustration: dict[str, int] = defaultdict(int)
    catchphrases: dict[str, int] = defaultdict(int)
    swear_quote_candidates: list[str] = []
    frustration_quote_candidates: list[str] = []
    for m in user_msgs:
        c = m.get("content") or ""
        if _count_swears(c):
            swear_quote_candidates.append(c)
        fr = _count_frustration(c)
        if fr:
            for k, v in fr.items():
                frustration[k] += v
            frustration_quote_candidates.append(c)
        for k, v in _count_catchphrases(c).items():
            catchphrases[k] += v

    def _truncate(s: str, max_len: int = 120) -> str:
        s = s.strip()
        return s[:max_len] if len(s) > max_len else s

    swear_quotes = [
        _truncate(s) for s in sorted(set(swear_quote_candidates), key=len)[:3]
    ]
    frustration_quotes = [
        _truncate(s) for s in sorted(set(frustration_quote_candidates), key=len)[:5]
    ]

    sorted_sessions = sorted(
        [
            (sid, s) for sid, s in sessions.items()
            if s["start"] is not None
        ],
        key=lambda x: x[1]["start"] or datetime.min,
    )
    max_clean_streak = 0
    curr_streak = 0
    for sid, _ in sorted_sessions:
        if session_swears.get(sid, 0) == 0:
            curr_streak += 1
        else:
            max_clean_streak = max(max_clean_streak, curr_streak)
            curr_streak = 0
    max_clean_streak = max(max_clean_streak, curr_streak)

    longest_session_messages = 0
    for s in sessions.values():
        longest_session_messages = max(longest_session_messages, len(s["messages"]))

    daily_counts: dict[str, int] = defaultdict(int)
    for m in messages:
        ts = _parse_ts(m.get("timestamp"))
        if ts:
            daily_counts[_date_str(ts)] += 1
    busiest_day = ""
    busiest_day_messages = 0
    for d, c in daily_counts.items():
        if c > busiest_day_messages:
            busiest_day_messages = c
            busiest_day = d

    top_frustration = dict(
        sorted(frustration.items(), key=lambda x: -x[1])[:10]
    )
    top_catchphrases = dict(
        sorted(catchphrases.items(), key=lambda x: -x[1])[:10]
    )

    return {
        "swear_count": swear_count,
        "peak_session_swears": peak_session_swears if session_swears else 0,
        "frustration_phrases": top_frustration,
        "catchphrases": top_catchphrases,
        "frustration_quotes": frustration_quotes,
        "swear_quotes": swear_quotes,
        "max_clean_streak": max_clean_streak,
        "total_user_chars": total_user_chars,
        "novels_equivalent": round(total_user_chars / 500_000, 2),
        "longest_session_messages": longest_session_messages,
        "busiest_day": busiest_day,
        "busiest_day_messages": busiest_day_messages,
    }


def compute_all_metrics(messages: list[dict]) -> dict:
    if not messages:
        return _empty_metrics()

    user_msgs = [m for m in messages if m.get("role") == "user"]
    assistant_msgs = [m for m in messages if m.get("role") == "assistant"]
    total_tool_calls = sum(len(m.get("tool_calls") or []) for m in messages)
    total_output_chars = sum(m.get("output_chars", 0) for m in messages)

    sessions = _build_session_map(messages)
    total_sessions = len(sessions)

    project_counts: dict[str, int] = defaultdict(int)
    project_first: dict[str, str] = {}
    project_last: dict[str, str] = {}
    for m in messages:
        p = m.get("project") or "unknown"
        if p == "unknown":
            continue
        project_counts[p] += 1
        ts = _parse_ts(m.get("timestamp"))
        if ts:
            d = _date_str(ts)
            if p not in project_first or d < project_first[p]:
                project_first[p] = d
            if p not in project_last or d > project_last[p]:
                project_last[p] = d

    projects = [
        {"project": p, "messages": c, "first": project_first.get(p, ""), "last": project_last.get(p, "")}
        for p, c in project_counts.items()
        if c >= 5
    ]
    projects.sort(key=lambda x: -x["messages"])

    autonomy = (len(assistant_msgs) + total_tool_calls) / len(user_msgs) if user_msgs else 0.0
    output_density = total_output_chars / len(user_msgs) if user_msgs else 0.0

    dates_with_ts = [_parse_ts(m.get("timestamp")) for m in messages if m.get("timestamp")]
    dates_with_ts = [d for d in dates_with_ts if d is not None]
    date_range_start = _date_str(min(dates_with_ts)) if dates_with_ts else ""
    date_range_end = _date_str(max(dates_with_ts)) if dates_with_ts else ""

    concurrency = _concurrency_metrics(sessions)

    autonomy_by_week: dict[str, list[tuple[int, int]]] = defaultdict(lambda: [0, 0])
    output_density_by_week: dict[str, list] = defaultdict(lambda: [0, 0])
    prompt_depth_by_week: dict[str, list[int]] = defaultdict(list)
    model_by_week: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for m in messages:
        ts = _parse_ts(m.get("timestamp"))
        if not ts:
            continue
        w = _week_str(ts)
        role = m.get("role")
        tc = len(m.get("tool_calls") or [])
        if role == "user":
            autonomy_by_week[w][0] += 1
            output_density_by_week[w][1] += 1
            prompt_depth_by_week[w].append(len(m.get("content") or ""))
        elif role == "assistant":
            autonomy_by_week[w][1] += 1 + tc
            output_density_by_week[w][0] += m.get("output_chars", 0)
            model = m.get("model") or "unknown"
            model_by_week[w][model] = model_by_week[w].get(model, 0) + 1

    autonomy_timeline = {}
    for w, (user_c, assist_c) in autonomy_by_week.items():
        if user_c > 0:
            autonomy_timeline[w] = round(assist_c / user_c, 2)

    output_density_timeline = {}
    for w, (chars, user_c) in output_density_by_week.items():
        if user_c > 0:
            output_density_timeline[w] = round(chars / user_c)

    prompt_depth_timeline = {}
    for w, lengths in prompt_depth_by_week.items():
        if lengths:
            prompt_depth_timeline[w] = round(sum(lengths) / len(lengths))

    model_evolution = {w: dict(counts) for w, counts in model_by_week.items()}

    growth = _growth_scorecard(sessions, messages)
    personality = _personality_metrics(messages, sessions)

    return {
        "hero": {
            "total_messages": len(messages),
            "user_messages": len(user_msgs),
            "assistant_messages": len(assistant_msgs),
            "total_tool_calls": total_tool_calls,
            "total_sessions": total_sessions,
            "total_projects": len(project_counts),
            "autonomy_ratio": round(autonomy, 2),
            "output_density": round(output_density),
            "total_output_chars": total_output_chars,
            "date_range_start": date_range_start,
            "date_range_end": date_range_end,
        },
        "concurrency": concurrency,
        "autonomy_timeline": autonomy_timeline,
        "output_density_timeline": output_density_timeline,
        "prompt_depth_timeline": prompt_depth_timeline,
        "model_evolution": model_evolution,
        "growth_scorecard": growth,
        "projects": projects,
        "personality": personality,
    }


def _empty_metrics() -> dict:
    return {
        "hero": {
            "total_messages": 0,
            "user_messages": 0,
            "assistant_messages": 0,
            "total_tool_calls": 0,
            "total_sessions": 0,
            "total_projects": 0,
            "autonomy_ratio": 0.0,
            "output_density": 0,
            "total_output_chars": 0,
            "date_range_start": "",
            "date_range_end": "",
        },
        "concurrency": {
            "peak_concurrent": 0,
            "peak_time": None,
            "avg_daily_peak": 0.0,
            "median_daily_peak": 0,
            "weekly_avg_peak": {},
            "distribution": {},
        },
        "autonomy_timeline": {},
        "output_density_timeline": {},
        "prompt_depth_timeline": {},
        "model_evolution": {},
        "growth_scorecard": {
            "avg_prompt_length": {"early": 0, "recent": 0, "change_pct": 0.0},
            "files_per_session": {"early": 0, "recent": 0, "change_pct": 0.0},
            "autonomy_ratio": {"early": 0.0, "recent": 0.0, "change_pct": 0.0},
            "msgs_per_session": {"early": 0, "recent": 0, "change_pct": 0.0},
            "tool_calls_per_session": {"early": 0, "recent": 0, "change_pct": 0.0},
            "output_density": {"early": 0, "recent": 0, "change_pct": 0.0},
        },
        "projects": [],
        "personality": {
            "swear_count": 0,
            "peak_session_swears": 0,
            "frustration_phrases": {},
            "catchphrases": {},
            "frustration_quotes": [],
            "swear_quotes": [],
            "max_clean_streak": 0,
            "total_user_chars": 0,
            "novels_equivalent": 0.0,
            "longest_session_messages": 0,
            "busiest_day": "",
            "busiest_day_messages": 0,
        },
    }
