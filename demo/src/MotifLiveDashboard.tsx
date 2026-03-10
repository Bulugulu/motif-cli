import React from "react";
import { AbsoluteFill, useCurrentFrame, interpolate } from "remotion";

const FONT =
  '"Cascadia Code", "SF Mono", "Fira Code", "JetBrains Mono", Consolas, monospace';

const C = {
  bg: "#0d1117",
  termBg: "#161b22",
  chrome: "#21262d",
  border: "#30363d",
  text: "#e6edf3",
  dim: "#8b949e",
  green: "#7ee787",
  brightGreen: "#3fb950",
  blue: "#79c0ff",
  orange: "#d29922",
  cursor: "#58a6ff",
  red: "#f85149",
  panelBlue: "#58a6ff",
  purple: "#d2a8ff",
};

export const LIVE_DURATION_IN_FRAMES = 500;

const TYPING_SPEED = 1.2;
const LINE_HEIGHT = 22;
const BAR_CHARS = 16;
const COMMAND = "motif live";
const COMMAND_START = 15;
const DASH_APPEAR = 48;
const SUMMARY_START = 355;
const BRANDING_START = 435;

const CLAMP = {
  extrapolateLeft: "clamp" as const,
  extrapolateRight: "clamp" as const,
};

// ─── Threshold-based coloring ───────────────────────────────────────

const THRESHOLDS: Record<string, Record<string, number>> = {
  concurrency: { yellow: 1, green: 2, purple: 4 },
  aipm: { yellow: 100, green: 1500, purple: 6000 },
  aipm_per_agent: { yellow: 100, green: 1500, purple: 6000 },
};

function thresholdColor(metric: string, value: number): string {
  const t = THRESHOLDS[metric];
  if (!t) return C.dim;
  if (value >= t.purple) return C.purple;
  if (value >= t.green) return C.green;
  if (value >= t.yellow) return C.orange;
  return C.red;
}

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(Math.round(n));
}

// ─── Animated metric keyframes ──────────────────────────────────────

interface MetricSnapshot {
  concurrency: number;
  avgConcurrency: number;
  aipm: number;
  sessionAipm: number;
  aipmPerAgent: number;
  sessionTokens: number;
  sessionMinutes: number;
  prompts: number;
  peakAipm: number;
  peakConcurrency: number;
}

function computeMetrics(frame: number): MetricSnapshot {
  const D = DASH_APPEAR;

  const concurrency = Math.round(
    interpolate(
      frame,
      [D, 88, 91, 188, 191, 243, 246, 255, 258, 340, 343],
      [0, 0, 1, 1, 2, 2, 3, 3, 2, 2, 0],
      CLAMP,
    ),
  );

  const avgConcurrency =
    Math.round(
      interpolate(
        frame,
        [D, 110, 160, 210, 260, 340],
        [0, 0.4, 0.8, 1.2, 1.6, 1.8],
        CLAMP,
      ) * 10,
    ) / 10;

  let aipm = interpolate(
    frame,
    [D, 88, 108, 140, 175, 195, 235, 268, 295, 325, 340, 343],
    [0, 0, 500, 2000, 3200, 3000, 6800, 8500, 5200, 4200, 4200, 0],
    CLAMP,
  );
  if (frame >= 295 && frame <= 340) {
    aipm += Math.sin(frame * 0.35) * 350;
  }
  aipm = Math.max(0, aipm);

  const sessionAipm = interpolate(
    frame,
    [D, 110, 160, 210, 260, 340],
    [0, 300, 1100, 2000, 2600, 2800],
    CLAMP,
  );

  const aipmPerAgent = interpolate(
    frame,
    [191, 218, 248, 278, 322, 340],
    [3200, 3400, 4300, 2700, 2100, 2100],
    CLAMP,
  );

  const sessionTokens = interpolate(
    frame,
    [D, 110, 160, 210, 260, 310, 340],
    [0, 2200, 9000, 20000, 33000, 43000, 48200],
    CLAMP,
  );

  const sessionMinutes = interpolate(frame, [D, 340], [0, 12], CLAMP);

  const prompts = Math.round(
    interpolate(
      frame,
      [D, 92, 122, 152, 192, 222, 252, 288, 328],
      [0, 1, 2, 3, 4, 5, 6, 7, 8],
      CLAMP,
    ),
  );

  const peakAipm = interpolate(
    frame,
    [D, 88, 108, 140, 175, 235, 268],
    [0, 0, 500, 2000, 3200, 6800, 8500],
    CLAMP,
  );

  const peakConcurrency = Math.round(
    interpolate(frame, [D, 91, 191, 246], [0, 1, 2, 3], CLAMP),
  );

  return {
    concurrency,
    avgConcurrency,
    aipm,
    sessionAipm,
    aipmPerAgent,
    sessionTokens,
    sessionMinutes,
    prompts,
    peakAipm,
    peakConcurrency,
  };
}

const FINAL_METRICS = computeMetrics(340);

// ─── Sub-components ─────────────────────────────────────────────────

const WindowChrome: React.FC = () => (
  <div
    style={{
      height: 40,
      backgroundColor: C.chrome,
      display: "flex",
      alignItems: "center",
      paddingLeft: 16,
      gap: 8,
      borderBottom: `1px solid ${C.border}`,
    }}
  >
    {["#ff5f57", "#febc2e", "#28c840"].map((bg) => (
      <div
        key={bg}
        style={{
          width: 12,
          height: 12,
          borderRadius: 6,
          backgroundColor: bg,
        }}
      />
    ))}
    <span
      style={{
        marginLeft: 16,
        fontFamily: FONT,
        fontSize: 12,
        color: C.dim,
        letterSpacing: 0.3,
      }}
    >
      Terminal — motif live
    </span>
  </div>
);

const MetricRow: React.FC<{
  label: string;
  value: number;
  maxValue: number;
  displayText: string;
  metricKey: string;
}> = ({ label, value, maxValue, displayText, metricKey }) => {
  const color = thresholdColor(metricKey, value);
  const filled =
    maxValue > 0
      ? Math.min(Math.round((value / maxValue) * BAR_CHARS), BAR_CHARS)
      : 0;

  return (
    <div style={{ height: LINE_HEIGHT, whiteSpace: "pre", fontSize: 14 }}>
      <span style={{ color: C.text }}>{"  "}</span>
      <span style={{ color: C.text }}>{label.padEnd(13)}</span>
      <span style={{ color }}>{"█".repeat(filled)}</span>
      <span style={{ color: C.border }}>{"░".repeat(BAR_CHARS - filled)}</span>
      <span style={{ color: C.text }}>{"  "}{displayText.padEnd(14)}</span>
      <span style={{ color, fontSize: 12 }}>●</span>
    </div>
  );
};

const DashboardPanel: React.FC<{
  metrics: MetricSnapshot;
  frame: number;
}> = ({ metrics: m, frame }) => {
  const aipmMax = 9000;

  let peakAgo = "";
  if (frame > 268) {
    const currentMin = interpolate(frame, [DASH_APPEAR, 340], [0, 12], CLAMP);
    const peakMin = interpolate(268, [DASH_APPEAR, 340], [0, 12], CLAMP);
    const ago = Math.max(1, Math.round(currentMin - peakMin));
    peakAgo = `(${ago}m ago)`;
  }

  const glowRadius = interpolate(frame, [215, 245, 275], [0, 14, 0], CLAMP);

  return (
    <div
      style={{
        border: `1.5px solid ${C.panelBlue}`,
        borderRadius: 8,
        padding: "14px 4px 10px",
        position: "relative",
        marginTop: 10,
        boxShadow:
          glowRadius > 0 ? `0 0 ${glowRadius}px ${C.purple}50` : "none",
      }}
    >
      <div
        style={{
          position: "absolute",
          top: -11,
          left: "50%",
          transform: "translateX(-50%)",
          backgroundColor: C.termBg,
          padding: "0 14px",
          fontFamily: FONT,
          fontSize: 13,
          fontWeight: 700,
          color: C.text,
          letterSpacing: 1.5,
        }}
      >
        MOTIF LIVE
      </div>

      <MetricRow
        label="CONCURRENCY"
        value={m.concurrency}
        maxValue={5}
        displayText={String(m.concurrency)}
        metricKey="concurrency"
      />
      <MetricRow
        label="AVG CONC"
        value={m.avgConcurrency}
        maxValue={5}
        displayText={m.avgConcurrency.toFixed(1)}
        metricKey="concurrency"
      />
      <MetricRow
        label="AIPM"
        value={m.aipm}
        maxValue={aipmMax}
        displayText={`${formatTokens(m.aipm)} tok/m`}
        metricKey="aipm"
      />
      <MetricRow
        label="AVG AIPM"
        value={m.sessionAipm}
        maxValue={aipmMax}
        displayText={`${formatTokens(m.sessionAipm)} tok/m`}
        metricKey="aipm"
      />
      {m.concurrency > 1 ? (
        <MetricRow
          label="/AGENT"
          value={m.aipmPerAgent}
          maxValue={aipmMax}
          displayText={`${formatTokens(m.aipmPerAgent)} tok/m`}
          metricKey="aipm_per_agent"
        />
      ) : (
        <div style={{ height: LINE_HEIGHT }} />
      )}

      <div style={{ height: 6 }} />

      <div
        style={{
          height: LINE_HEIGHT,
          whiteSpace: "pre",
          color: C.dim,
          fontSize: 12,
          paddingLeft: 14,
        }}
      >
        {`Session: ${Math.round(m.sessionMinutes)}m  │  Total: ${formatTokens(m.sessionTokens)} tokens  │  Prompts: ${m.prompts}`}
      </div>

      <div style={{ height: 6 }} />

      <div
        style={{
          whiteSpace: "pre",
          color: C.dim,
          fontSize: 12,
          paddingLeft: 14,
          lineHeight: "20px",
        }}
      >
        <div>
          {`Peak AIPM: ${formatTokens(m.peakAipm)}${peakAgo ? ` ${peakAgo}` : ""}`}
        </div>
        <div>{`Peak Concurrency: ${m.peakConcurrency}`}</div>
      </div>

      {m.concurrency === 0 && m.aipm === 0 && frame < 340 && (
        <div
          style={{
            height: LINE_HEIGHT,
            whiteSpace: "pre",
            color: C.dim,
            fontSize: 12,
            paddingLeft: 14,
            opacity: 0.6,
            fontStyle: "italic",
            marginTop: 4,
          }}
        >
          Watching for AI activity...
        </div>
      )}
    </div>
  );
};

const SummaryPanel: React.FC<{ frame: number }> = ({ frame }) => {
  const m = FINAL_METRICS;
  const leverage = m.prompts > 0 ? m.sessionTokens / m.prompts : 0;
  const revealBase = SUMMARY_START + 18;

  const rows: [string, string][] = [
    ["Duration:", `${Math.round(m.sessionMinutes)}m`],
    ["AI Output:", `${formatTokens(m.sessionTokens)} tokens`],
    ["Avg AIPM:", formatTokens(m.sessionAipm)],
    ["Peak AIPM:", formatTokens(m.peakAipm)],
    ["Avg Concurrency:", m.avgConcurrency.toFixed(1)],
    ["Peak Concurrency:", String(m.peakConcurrency)],
    ["Prompts Sent:", String(m.prompts)],
    ["Leverage:", `${formatTokens(leverage)} tok/prompt`],
  ];

  return (
    <div
      style={{
        border: `1.5px solid ${C.panelBlue}`,
        borderRadius: 8,
        padding: "14px 16px 10px",
        position: "relative",
        marginTop: 10,
      }}
    >
      <div
        style={{
          position: "absolute",
          top: -11,
          left: "50%",
          transform: "translateX(-50%)",
          backgroundColor: C.termBg,
          padding: "0 14px",
          fontFamily: FONT,
          fontSize: 13,
          fontWeight: 700,
          color: C.brightGreen,
          letterSpacing: 1.5,
        }}
      >
        SESSION COMPLETE
      </div>

      {rows.map(([label, value], i) => (
        <div
          key={label}
          style={{
            height: LINE_HEIGHT,
            whiteSpace: "pre",
            fontSize: 13,
            opacity: interpolate(
              frame,
              [revealBase + i * 3, revealBase + i * 3 + 5],
              [0, 1],
              CLAMP,
            ),
          }}
        >
          <span style={{ color: C.dim }}>{"  "}{label.padEnd(20)}</span>
          <span style={{ color: C.text }}>{value}</span>
        </div>
      ))}
    </div>
  );
};

// ─── Main component ─────────────────────────────────────────────────

export const MotifLiveDashboard: React.FC = () => {
  const frame = useCurrentFrame();
  const cursorVisible = Math.floor(frame / 16) % 2 === 0;

  const cmdElapsed = Math.max(0, frame - COMMAND_START);
  const cmdCharsShown = Math.min(
    Math.floor(cmdElapsed * TYPING_SPEED),
    COMMAND.length,
  );
  const cmdDone = cmdCharsShown >= COMMAND.length;
  const showMonitoring =
    cmdDone &&
    frame >= COMMAND_START + Math.ceil(COMMAND.length / TYPING_SPEED) + 10;

  const dashboardOpacity = interpolate(
    frame,
    [DASH_APPEAR, DASH_APPEAR + 15, SUMMARY_START, SUMMARY_START + 10],
    [0, 1, 1, 0],
    CLAMP,
  );
  const summaryOpacity = interpolate(
    frame,
    [SUMMARY_START + 10, SUMMARY_START + 25],
    [0, 1],
    CLAMP,
  );

  const currentMetrics = computeMetrics(frame);
  const fadeIn = interpolate(frame, [0, 12], [0, 1], CLAMP);

  return (
    <AbsoluteFill
      style={{
        backgroundColor: C.bg,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontFamily: FONT,
        opacity: fadeIn,
      }}
    >
      <div
        style={{
          width: 720,
          height: 430,
          borderRadius: 12,
          overflow: "hidden",
          border: `1px solid ${C.border}`,
          boxShadow:
            "0 20px 60px rgba(0,0,0,0.5), 0 0 0 1px rgba(255,255,255,0.03)",
          display: "flex",
          flexDirection: "column",
        }}
      >
        <WindowChrome />

        <div
          style={{
            flex: 1,
            backgroundColor: C.termBg,
            padding: "14px 20px",
            fontSize: 14,
            lineHeight: `${LINE_HEIGHT}px`,
            overflow: "hidden",
          }}
        >
          <div
            style={{
              height: LINE_HEIGHT,
              whiteSpace: "pre",
              display: "flex",
            }}
          >
            <span style={{ color: C.green, fontWeight: 700 }}>$ </span>
            <span style={{ color: C.text }}>
              {COMMAND.slice(0, cmdCharsShown)}
            </span>
            {!cmdDone && cursorVisible && (
              <span style={{ color: C.cursor }}>█</span>
            )}
          </div>

          {showMonitoring && (
            <div
              style={{
                height: LINE_HEIGHT,
                whiteSpace: "pre",
                color: C.dim,
              }}
            >
              Monitoring ~/.motif/ for AI activity...
            </div>
          )}

          <div style={{ position: "relative" }}>
            {dashboardOpacity > 0 && (
              <div style={{ opacity: dashboardOpacity }}>
                <DashboardPanel metrics={currentMetrics} frame={frame} />
              </div>
            )}
            {summaryOpacity > 0 && (
              <div
                style={{
                  opacity: summaryOpacity,
                  position: dashboardOpacity > 0 ? "absolute" : "relative",
                  top: 0,
                  left: 0,
                  right: 0,
                }}
              >
                <SummaryPanel frame={frame} />
              </div>
            )}
          </div>
        </div>
      </div>

      <div
        style={{
          position: "absolute",
          bottom: 14,
          right: 24,
          fontFamily: FONT,
          fontSize: 11,
          color: C.dim,
          opacity: interpolate(
            frame,
            [BRANDING_START, BRANDING_START + 30],
            [0, 0.6],
            CLAMP,
          ),
        }}
      >
        pip install motif-cli
      </div>
    </AbsoluteFill>
  );
};
