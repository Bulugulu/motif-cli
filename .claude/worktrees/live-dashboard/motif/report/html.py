"""
HTML report generation for the Vibe Report.

Generates a self-contained, shareable HTML page — "Spotify Wrapped for vibe coding."
"""

import json
import re
from datetime import datetime, timedelta
from typing import Any


def _week_to_label(week_str: str) -> str:
    """Convert week string like '2025-W06' to 'Feb 2025' (Monday of that week).

    Handles both ISO (%V) and US (%U) week formats from metrics.
    """
    m = re.match(r"(\d{4})-W(\d{1,2})", week_str)
    if not m:
        return week_str
    year, week = int(m.group(1)), int(m.group(2))
    try:
        d = datetime.strptime(f"{year}-W{week:02d}-1", "%G-W%V-%u")
        return d.strftime("%b %Y")
    except (ValueError, TypeError):
        pass
    try:
        first_jan = datetime(year, 1, 1)
        if week == 0:
            return first_jan.strftime("%b %Y")
        days_to_sunday = (6 - first_jan.weekday() + 7) % 7
        first_sunday = first_jan + timedelta(days=days_to_sunday)
        week_start = first_sunday + timedelta(weeks=week - 1)
        monday = week_start + timedelta(days=1)
        return monday.strftime("%b %Y")
    except (ValueError, TypeError):
        return week_str


def _format_date_range(start: str, end: str) -> str:
    """Format date range as 'Feb 2025 — Mar 2026'."""
    if not start or not end:
        return ""
    try:
        ds = datetime.strptime(start[:10], "%Y-%m-%d")
        de = datetime.strptime(end[:10], "%Y-%m-%d")
        return f"{ds.strftime('%b %Y')} — {de.strftime('%b %Y')}"
    except (ValueError, TypeError):
        return f"{start} — {end}"


def _swear_context(count: int) -> str:
    """Return playful context for swear count."""
    if count <= 10:
        return "Saint"
    if count <= 50:
        return "Mostly composed"
    if count <= 200:
        return "Has opinions"
    return "Passionate debugger"


def _safe_metrics(metrics: dict) -> dict:
    """Ensure metrics has all expected keys with safe defaults."""
    hero = metrics.get("hero") or {}
    concurrency = metrics.get("concurrency") or {}
    autonomy_timeline = metrics.get("autonomy_timeline") or {}
    prompt_depth_timeline = metrics.get("prompt_depth_timeline") or {}
    model_evolution = metrics.get("model_evolution") or {}
    growth_scorecard = metrics.get("growth_scorecard") or {}
    projects = metrics.get("projects") or []
    personality = metrics.get("personality") or {}

    return {
        "hero": {
            "total_messages": hero.get("total_messages", 0),
            "user_messages": hero.get("user_messages", 0),
            "assistant_messages": hero.get("assistant_messages", 0),
            "total_tool_calls": hero.get("total_tool_calls", 0),
            "total_sessions": hero.get("total_sessions", 0),
            "total_projects": hero.get("total_projects", 0),
            "autonomy_ratio": hero.get("autonomy_ratio", 0.0),
            "date_range_start": hero.get("date_range_start", ""),
            "date_range_end": hero.get("date_range_end", ""),
        },
        "concurrency": {
            "peak_concurrent": concurrency.get("peak_concurrent", 0),
            "peak_time": concurrency.get("peak_time"),
            "avg_daily_peak": concurrency.get("avg_daily_peak", 0.0),
            "median_daily_peak": concurrency.get("median_daily_peak", 0),
            "weekly_avg_peak": concurrency.get("weekly_avg_peak") or {},
            "distribution": concurrency.get("distribution") or {},
        },
        "autonomy_timeline": autonomy_timeline,
        "prompt_depth_timeline": prompt_depth_timeline,
        "model_evolution": model_evolution,
        "growth_scorecard": growth_scorecard,
        "projects": projects[:15],
        "personality": {
            "swear_count": personality.get("swear_count", 0),
            "peak_session_swears": personality.get("peak_session_swears", 0),
            "frustration_phrases": personality.get("frustration_phrases") or {},
            "catchphrases": personality.get("catchphrases") or {},
            "frustration_quotes": personality.get("frustration_quotes") or [],
            "swear_quotes": personality.get("swear_quotes") or [],
            "max_clean_streak": personality.get("max_clean_streak", 0),
            "total_user_chars": personality.get("total_user_chars", 0),
            "novels_equivalent": personality.get("novels_equivalent", 0.0),
            "longest_session_messages": personality.get("longest_session_messages", 0),
            "busiest_day": personality.get("busiest_day", ""),
            "busiest_day_messages": personality.get("busiest_day_messages", 0),
        },
    }


def generate_html_report(metrics: dict, archetype: dict | None = None, user_name: str = "Vibe Coder") -> str:
    """Generate a self-contained HTML report from computed metrics.

    Args:
        metrics: Output from metrics.compute_all_metrics()
        archetype: Optional dict with "name" and "description" keys from LLM analysis
        user_name: Display name for the report (default "Vibe Coder")

    Returns:
        Complete HTML string ready to write to file.
    """
    m = _safe_metrics(metrics)
    hero = m["hero"]
    concurrency = m["concurrency"]
    autonomy_timeline = m["autonomy_timeline"]
    growth_scorecard = m["growth_scorecard"]
    projects = m["projects"]
    personality = m["personality"]

    date_range = _format_date_range(hero["date_range_start"], hero["date_range_end"])
    autonomy_str = f"{hero['autonomy_ratio']:.1f}x" if hero["autonomy_ratio"] else "0x"
    peak_str = f"{concurrency['peak_concurrent']} session{'s' if concurrency['peak_concurrent'] != 1 else ''}"

    # Open Graph description
    og_desc = (
        f"{hero['total_sessions']} sessions, {autonomy_str} autonomy ratio. "
        "Your vibe coding journey, visualized."
    )

    # JSON for charts (ensure serializable)
    def _json_serial(obj: Any) -> Any:
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

    metrics_json = json.dumps(m, default=_json_serial)

    # Growth metric config
    growth_config = [
        ("avg_prompt_length", "Specification Depth", "longer = more detailed specs = better delegation"),
        ("autonomy_ratio", "Autonomy Ratio", "higher = more agent work per human message"),
        ("msgs_per_session", "Session Depth", "more messages = tackling bigger tasks"),
        ("tool_calls_per_session", "Tool Density", "more tool calls = agent doing more work"),
    ]

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta property="og:title" content="{user_name}'s Vibe Coding Report — Motif">
  <meta property="og:description" content="{og_desc}">
  <meta property="og:type" content="website">
  <title>Vibe Report — Motif</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
  <style>
    :root {{
      --bg: #0d1117;
      --card: #161b22;
      --border: #30363d;
      --primary: #58a6ff;
      --secondary: #3fb950;
      --warning: #d29922;
      --danger: #f85149;
      --purple: #bc8cff;
      --muted: #8b949e;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      padding: 24px;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
      background: var(--bg);
      color: var(--muted);
      line-height: 1.5;
    }}
    .container {{ max-width: 900px; margin: 0 auto; }}
    h1 {{ font-size: 2.5rem; font-weight: 700; color: #fff; margin: 0 0 8px 0; }}
    h2 {{ font-size: 1.5rem; font-weight: 600; color: #fff; margin: 0 0 8px 0; }}
    .subtitle {{ font-size: 0.95rem; color: var(--muted); margin-bottom: 24px; }}
    .card {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 24px;
      margin-bottom: 24px;
    }}
    .hero-stats {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
      gap: 16px;
      margin-top: 24px;
    }}
    .stat-box {{
      background: rgba(88, 166, 255, 0.08);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 16px;
      text-align: center;
    }}
    .stat-box .value {{ font-size: 1.75rem; font-weight: 700; color: var(--primary); }}
    .stat-box .label {{ font-size: 0.8rem; color: var(--muted); margin-top: 4px; }}
    .archetype-badge {{
      margin-top: 20px;
      padding: 20px;
      border: 2px solid var(--purple);
      border-radius: 12px;
      background: rgba(188, 140, 255, 0.06);
    }}
    .archetype-badge .name {{ font-size: 1.25rem; font-weight: 600; color: var(--purple); }}
    .archetype-badge .desc {{ font-size: 0.9rem; color: var(--muted); font-style: italic; margin-top: 8px; }}
    .chart-wrap {{ position: relative; height: 280px; margin: 16px 0; }}
    .callout {{ font-size: 0.9rem; color: var(--secondary); margin-top: 12px; padding: 12px; background: rgba(63, 185, 80, 0.08); border-radius: 8px; }}
    .constellation-wrap {{
      position: relative;
      width: 100%;
      height: 400px;
      background: radial-gradient(ellipse at center, #0d1117 0%, #010409 100%);
      border-radius: 12px;
      overflow: hidden;
      margin-top: 16px;
    }}
    .constellation-wrap .star {{
      position: absolute;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-direction: column;
      text-align: center;
      cursor: default;
      transition: transform 0.2s;
    }}
    .constellation-wrap .star:hover {{
      transform: scale(1.15);
      z-index: 10;
    }}
    .constellation-wrap .star .star-name {{
      font-size: 0.7rem;
      color: #fff;
      font-weight: 600;
      text-shadow: 0 1px 3px rgba(0,0,0,0.8);
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      max-width: 90%;
    }}
    .constellation-wrap .star .star-count {{
      font-size: 0.6rem;
      color: rgba(255,255,255,0.7);
    }}
    .growth-table {{ width: 100%; border-collapse: collapse; }}
    .growth-table th, .growth-table td {{ padding: 12px; text-align: left; border-bottom: 1px solid var(--border); }}
    .growth-table th {{ color: var(--muted); font-weight: 500; font-size: 0.85rem; }}
    .growth-table .change-up {{ color: var(--secondary); }}
    .growth-table .change-down {{ color: var(--danger); }}
    .personality-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
      gap: 16px;
      margin-top: 16px;
    }}
    .personality-card {{
      background: rgba(63, 185, 80, 0.06);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 16px;
      text-align: center;
    }}
    .personality-card .value {{ font-size: 1.5rem; font-weight: 700; color: var(--secondary); }}
    .personality-card .label {{ font-size: 0.8rem; color: var(--muted); margin-top: 4px; }}
    .footer {{ text-align: center; padding: 32px 0; font-size: 0.85rem; color: var(--muted); }}
    .footer a {{ color: var(--primary); text-decoration: none; }}
    .footer a:hover {{ text-decoration: underline; }}
    @media (max-width: 600px) {{
      body {{ padding: 16px; }}
      .card {{ padding: 16px; }}
      h1 {{ font-size: 1.75rem; }}
    }}
  </style>
</head>
<body>
  <div class="container">
    <!-- 1. Hero Card -->
    <section class="card">
      <h1>Vibe Report</h1>
      <p style="font-size: 1.1rem; color: #fff; margin: 4px 0 0 0;">{user_name}'s Vibe Report</p>
      <p class="subtitle">Generated by <a href="https://github.com/avivsheriff/motif-cli" target="_blank" rel="noopener" style="color: var(--primary);">Motif</a></p>
      {f'<p class="subtitle">{date_range}</p>' if date_range else ''}
      <div class="hero-stats">
        <div class="stat-box">
          <div class="value">{hero["total_sessions"]}</div>
          <div class="label">Total Sessions</div>
        </div>
        <div class="stat-box">
          <div class="value">{hero["total_projects"]}</div>
          <div class="label">Projects</div>
        </div>
        <div class="stat-box">
          <div class="value">{autonomy_str}</div>
          <div class="label">Autonomy Ratio</div>
        </div>
        <div class="stat-box">
          <div class="value">{peak_str}</div>
          <div class="label">Peak Concurrency</div>
        </div>
      </div>
'''

    if archetype and archetype.get("name"):
        arch_name = archetype.get("name", "")
        arch_desc = archetype.get("description", "")
        html += f'''
      <div class="archetype-badge">
        <div class="name">{arch_name}</div>
        {f'<div class="desc">{arch_desc}</div>' if arch_desc else ''}
      </div>
'''

    html += '''
    </section>

    <!-- 2. Agent Concurrency -->
    <section class="card">
      <h2>Agent Concurrency</h2>
      <p class="subtitle">The strongest correlate of AI-assisted productivity. <a href="https://metr.substack.com/p/2026-02-17-exploratory-transcript-analysis-for-estimating-time-savings-from-coding-agents" target="_blank" rel="noopener" style="color: var(--primary);">METR's transcript analysis</a> found that a developer averaging 2.3+ concurrent agent sessions achieved ~12× time savings, while those running ~1 session averaged ~2×.</p>
      <div class="chart-wrap"><canvas id="chart-concurrency"></canvas></div>
      <div id="callout-concurrency" class="callout"></div>
    </section>

    <!-- 3. Autonomy Ratio -->
    <section class="card">
      <h2>Autonomy Ratio</h2>
      <p class="subtitle">Agent actions per human message. Higher means more effective delegation.</p>
      <div class="chart-wrap"><canvas id="chart-autonomy"></canvas></div>
      <div id="callout-autonomy" class="callout"></div>
    </section>

    <!-- 4. Project Constellation -->
    <section class="card">
      <h2>Project Constellation</h2>
      <p class="subtitle">Your coding galaxy — each star sized by message count</p>
      <div class="constellation-wrap" id="constellation"></div>
    </section>

    <!-- 5. Growth Scorecard -->
    <section class="card">
      <h2>How You've Grown</h2>
      <p class="subtitle">Comparing your first 25% of sessions to your most recent 25%</p>
      <table class="growth-table" id="growth-table"></table>
    </section>

    <!-- 7. Personality & Fun Stats -->
    <section class="card">
      <h2>Your Vibe, Decoded</h2>
      <p class="subtitle">The numbers behind your coding personality</p>
      <div class="personality-grid" id="personality-grid"></div>
    </section>

    <!-- 8. Footer -->
    <footer class="footer">
      <p>Generated by <a href="https://github.com/avivsheriff/motif-cli" target="_blank" rel="noopener">Motif</a></p>
      <p>Your data never left your machine.</p>
      <p><small>''' + timestamp + '''</small></p>
    </footer>
  </div>

  <script>
    const METRICS = ''' + metrics_json + ''';

    function weekToLabel(weekStr) {
      const m = weekStr.match(/(\\d{4})-W(\\d{1,2})/);
      if (!m) return weekStr;
      const year = parseInt(m[1], 10), week = parseInt(m[2], 10);
      const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
      if (week === 0) {
        const d = new Date(year, 0, 1);
        return months[d.getMonth()] + " " + d.getFullYear();
      }
      const jan1 = new Date(year, 0, 1);
      const dayOfWeek = jan1.getDay();
      const daysToFirstSunday = dayOfWeek === 0 ? 0 : 7 - dayOfWeek;
      const firstSunday = new Date(year, 0, 1 + daysToFirstSunday);
      const weekStart = new Date(firstSunday.getTime());
      weekStart.setDate(weekStart.getDate() + (week - 1) * 7);
      const monday = new Date(weekStart.getTime());
      monday.setDate(monday.getDate() + 1);
      return months[monday.getMonth()] + " " + monday.getFullYear();
    }

    function chartDefaults() {
      return {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 800 },
        plugins: {
          legend: { labels: { color: "#8b949e" } }
        },
        scales: {
          x: {
            grid: { color: "#30363d" },
            ticks: { color: "#8b949e", maxRotation: 45 }
          },
          y: {
            grid: { color: "#30363d" },
            ticks: { color: "#8b949e" }
          }
        }
      };
    }

    document.addEventListener("DOMContentLoaded", function() {
      const conv = METRICS.concurrency.weekly_avg_peak || {};
      const weeks = Object.keys(conv).sort();
      const labels = weeks.map(weekToLabel);
      const values = weeks.map(w => conv[w]);

      // Concurrency chart
      if (weeks.length > 0) {
        new Chart(document.getElementById("chart-concurrency"), {
          type: "line",
          data: {
            labels,
            datasets: [{
              label: "Avg peak concurrency",
              data: values,
              borderColor: "#58a6ff",
              backgroundColor: "rgba(88, 166, 255, 0.2)",
              fill: true,
              tension: 0.4
            }]
          },
          options: {
            ...chartDefaults(),
            plugins: { legend: { display: false } }
          }
        });
        const firstAvg = values.slice(0, 3).reduce((a,b)=>a+b,0) / Math.min(3, values.length);
        const lastAvg = values.slice(-3).reduce((a,b)=>a+b,0) / Math.min(3, values.length);
        const growth = firstAvg > 0 ? ((lastAvg - firstAvg) / firstAvg * 100).toFixed(0) : 0;
        document.getElementById("callout-concurrency").textContent =
          growth > 0 ? `From ~${firstAvg.toFixed(1)} to ~${lastAvg.toFixed(1)} concurrent sessions (${growth}% growth)` : "";
      }

      // Autonomy chart
      const auto = METRICS.autonomy_timeline || {};
      const autoWeeks = Object.keys(auto).sort();
      const autoLabels = autoWeeks.map(weekToLabel);
      const autoValues = autoWeeks.map(w => auto[w]);
      if (autoWeeks.length > 0) {
        new Chart(document.getElementById("chart-autonomy"), {
          type: "line",
          data: {
            labels: autoLabels,
            datasets: [{
              label: "Autonomy ratio",
              data: autoValues,
              borderColor: "#3fb950",
              backgroundColor: "rgba(63, 185, 80, 0.2)",
              fill: true,
              tension: 0.4
            }]
          },
          options: {
            ...chartDefaults(),
            plugins: { legend: { display: false } },
            scales: {
              ...chartDefaults().scales,
              y: {
                ...chartDefaults().scales.y,
                type: autoValues.some(v => v > 30) ? "logarithmic" : "linear"
              }
            }
          }
        });
        const aFirst = autoValues.slice(0, 3).reduce((a,b)=>a+b,0) / Math.min(3, autoValues.length);
        const aLast = autoValues.slice(-3).reduce((a,b)=>a+b,0) / Math.min(3, autoValues.length);
        const aGrowth = aFirst > 0 ? ((aLast - aFirst) / aFirst * 100).toFixed(0) : 0;
        document.getElementById("callout-autonomy").textContent =
          aGrowth > 0 ? `From ~${aFirst.toFixed(1)}x to ~${aLast.toFixed(1)}x autonomy (${aGrowth}% growth)` : "";
      }

      // Project constellation (galaxy)
      const projs = (METRICS.projects || []).slice(0, 15);
      const constellation = document.getElementById("constellation");
      if (projs.length > 0) {
        const maxMsgs = Math.max(...projs.map(p => p.messages || 0), 1);
        const containerW = constellation.clientWidth;
        const containerH = constellation.clientHeight;

        const cx = containerW / 2;
        const cy = containerH / 2;

        projs.forEach((p, i) => {
          const ratio = p.messages / maxMsgs;
          const size = Math.max(40, Math.min(120, 40 + ratio * 80));

          const angle = (i / projs.length) * Math.PI * 2 + (i * 0.5);
          const radius = 60 + (i / projs.length) * (Math.min(containerW, containerH) * 0.35);
          const x = cx + Math.cos(angle) * radius - size / 2;
          const y = cy + Math.sin(angle) * radius - size / 2;

          const hue = 200 + (i / projs.length) * 120;
          const saturation = 40 + ratio * 30;
          const lightness = 20 + ratio * 15;

          const star = document.createElement("div");
          star.className = "star";
          star.style.width = size + "px";
          star.style.height = size + "px";
          star.style.left = Math.max(0, Math.min(containerW - size, x)) + "px";
          star.style.top = Math.max(0, Math.min(containerH - size, y)) + "px";
          star.style.background = `radial-gradient(circle at 30% 30%, hsl(${hue}, ${saturation}%, ${lightness + 20}%), hsl(${hue}, ${saturation}%, ${lightness}%))`;
          star.style.boxShadow = `0 0 ${10 + ratio * 20}px hsl(${hue}, ${saturation}%, ${lightness + 10}%)`;
          star.title = `${p.project}: ${p.messages} messages (${p.first || "?"} — ${p.last || "?"})`;

          star.innerHTML = `<span class="star-name">${escapeHtml(p.project)}</span><span class="star-count">${p.messages}</span>`;
          constellation.appendChild(star);
        });

        for (let i = 0; i < 40; i++) {
          const dot = document.createElement("div");
          dot.style.cssText = `position: absolute; width: ${1 + Math.random() * 2}px; height: ${1 + Math.random() * 2}px; background: rgba(255,255,255,${0.2 + Math.random() * 0.4}); border-radius: 50%; left: ${Math.random() * 100}%; top: ${Math.random() * 100}%;`;
          constellation.appendChild(dot);
        }
      }

      // Growth scorecard
      const growthDefs = {
        "avg_prompt_length": "How detailed your instructions are. Longer specs = the agent has more context to work with, producing better first-try results.",
        "autonomy_ratio": "Agent actions (responses + tool calls) per human message. Higher = you're delegating more effectively.",
        "msgs_per_session": "Total back-and-forth per session. More messages often means you're tackling bigger, more complex tasks.",
        "tool_calls_per_session": "How many tools (file reads, edits, searches, commands) the agent uses per session. More = the agent is doing more work for you."
      };
      const growthConfig = [
        ["avg_prompt_length", "Specification Depth"],
        ["autonomy_ratio", "Autonomy Ratio"],
        ["msgs_per_session", "Session Depth"],
        ["tool_calls_per_session", "Tool Density"]
      ];
      const tbl = document.getElementById("growth-table");
      tbl.innerHTML = "<tr><th>Metric</th><th>Early</th><th>Recent</th><th>Change</th><th>Interpretation</th></tr>";
      const g = METRICS.growth_scorecard || {};
      growthConfig.forEach(([key, label]) => {
        const row = g[key];
        if (!row) return;
        const pct = row.change_pct || 0;
        const upGood = ["avg_prompt_length","autonomy_ratio","msgs_per_session","tool_calls_per_session"].includes(key);
        const improved = (pct > 0 && upGood) || (pct < 0 && !upGood);
        const cls = Math.abs(pct) < 5 ? "" : improved ? "change-up" : "change-down";
        const interp = Math.abs(pct) < 5 ? "Holding steady." : improved ? `Up ${Math.abs(pct).toFixed(0)}% — you're leveling up.` : `Down ${Math.abs(pct).toFixed(0)}% — room to grow.`;
        const tr = document.createElement("tr");
        tr.innerHTML = `<th>${escapeHtml(label)}</th><td>${formatVal(row.early)}</td><td>${formatVal(row.recent)}</td><td class="${cls}">${pct > 0 ? "+" : ""}${pct.toFixed(1)}%</td><td>${interp}</td>`;
        tbl.appendChild(tr);
        const defTr = document.createElement("tr");
        defTr.innerHTML = `<td colspan="5" style="padding: 4px 12px 16px 12px; font-size: 0.8rem; color: var(--muted); border-bottom: 1px solid var(--border);">${growthDefs[key] || ""}</td>`;
        tbl.appendChild(defTr);
      });

      // Personality grid
      const pers = METRICS.personality || {};
      const swearQuotes = pers.swear_quotes || [];
      const frustQuotes = pers.frustration_quotes || [];
      const allQuotes = [...swearQuotes, ...frustQuotes].slice(0, 2);
      const pg = document.getElementById("personality-grid");
      if (allQuotes.length > 0) {
        const quoteSection = document.createElement("div");
        quoteSection.style.cssText = "margin-bottom: 20px;";
        allQuotes.forEach(q => {
          const qEl = document.createElement("div");
          qEl.style.cssText = "background: rgba(248, 81, 73, 0.08); border-left: 3px solid var(--danger); padding: 12px 16px; margin-bottom: 8px; border-radius: 0 8px 8px 0; font-style: italic; color: var(--muted);";
          qEl.textContent = '"' + q + '"';
          quoteSection.appendChild(qEl);
        });
        pg.parentElement.insertBefore(quoteSection, pg);
      }
      const topFrust = Object.entries(pers.frustration_phrases || {})[0];
      const topCatch = Object.entries(pers.catchphrases || {})[0];
      const persItems = [
        { value: pers.swear_count, label: _swearContext(pers.swear_count) + " — total swears" },
        { value: pers.peak_session_swears, label: "swears in one session (peak frustration)" },
        { value: topFrust ? '"' + topFrust[0] + '"' : "—", label: topFrust ? "× " + topFrust[1] + " (top frustration phrase)" : "Top frustration phrase" },
        { value: topCatch ? '"' + topCatch[0] + '"' : "—", label: topCatch ? "× " + topCatch[1] + " (signature catchphrase)" : "Top catchphrase" },
        { value: pers.max_clean_streak, label: "sessions in a row without swearing" },
        { value: pers.novels_equivalent, label: "novels' worth of prompts typed to AI" },
        { value: pers.longest_session_messages, label: "messages in longest single session" },
        { value: pers.busiest_day || "—", label: (pers.busiest_day_messages || 0) + " messages (busiest day)" }
      ];
      persItems.forEach(({ value, label }) => {
        const card = document.createElement("div");
        card.className = "personality-card";
        const dispVal = typeof value === "number" ? (Number.isInteger(value) ? value : value.toFixed(1)) : value;
        card.innerHTML = `<div class="value">${escapeHtml(String(dispVal))}</div><div class="label">${escapeHtml(label)}</div>`;
        pg.appendChild(card);
      });
    });

    function escapeHtml(s) {
      if (s == null) return "";
      const div = document.createElement("div");
      div.textContent = s;
      return div.innerHTML;
    }
    function formatVal(v) {
      if (typeof v === "number") return Number.isInteger(v) ? v : v.toFixed(1);
      return v;
    }
    function _swearContext(c) {
      if (c <= 10) return "Saint";
      if (c <= 50) return "Mostly composed";
      if (c <= 200) return "Has opinions";
      return "Passionate debugger";
    }
  </script>
</body>
</html>
'''

    return html
