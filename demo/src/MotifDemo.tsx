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
};

const TYPING_SPEED = 1.0; // chars per frame at 30fps
const LINE_HEIGHT = 22;

// ─── Terminal session data ───────────────────────────────────────────

interface OutputLine {
  text: string;
  color: string;
  bold?: boolean;
}

interface Command {
  command: string;
  output: OutputLine[];
  lineDelay: number;
}

const SESSION: Command[] = [
  {
    command: "pip install motif-cli",
    output: [
      { text: "Collecting motif-cli", color: C.dim },
      { text: "  Downloading motif_cli-0.4.0-py3-none-any.whl", color: C.dim },
      {
        text: "Successfully installed motif-cli-0.4.0",
        color: C.brightGreen,
      },
    ],
    lineDelay: 10,
  },
  {
    command: "motif extract cursor",
    output: [
      { text: "Found 12 Cursor projects", color: C.text },
      { text: "  ✓ Edtech — 1,067 messages", color: C.brightGreen },
      { text: "  ✓ GameMarketer — 218 messages", color: C.brightGreen },
      { text: "  ✓ KangarooCourt — 386 messages", color: C.brightGreen },
      { text: "Saved to ~/.motif/conversations/", color: C.dim },
    ],
    lineDelay: 8,
  },
  {
    command: "motif analyze --prepare",
    output: [
      { text: "Loading: Edtech (1,067 messages)", color: C.text },
      {
        text: "Relevance filtering: 1,067 → 312 high-signal messages",
        color: C.blue,
      },
      { text: "Token budget: 50,000 tokens", color: C.dim },
      {
        text: "✓ Analysis file ready → ~/.motif/analysis-prep.md",
        color: C.brightGreen,
      },
    ],
    lineDelay: 10,
  },
  {
    command: "motif rules analysis.json",
    output: [
      {
        text: "✓ Generated CLAUDE.md — 8 rules, project context",
        color: C.brightGreen,
      },
      { text: "✓ Generated 5 skill files", color: C.brightGreen },
      {
        text: "✓ Generated report.md — summary & recommendations",
        color: C.brightGreen,
      },
      { text: "", color: C.text },
      { text: "Your AI now knows how you work.", color: C.orange, bold: true },
    ],
    lineDelay: 10,
  },
];

// ─── Timeline computation ────────────────────────────────────────────

interface RenderedLine {
  text: string;
  color: string;
  prefix?: string;
  prefixColor?: string;
  bold?: boolean;
  typed?: boolean;
  typeSpeed?: number;
  appearFrame: number;
}

function buildTimeline(): RenderedLine[] {
  const lines: RenderedLine[] = [];
  let frame = 20;

  for (const cmd of SESSION) {
    // Command line (typed)
    lines.push({
      text: cmd.command,
      color: C.text,
      prefix: "$ ",
      prefixColor: C.green,
      typed: true,
      typeSpeed: TYPING_SPEED,
      appearFrame: frame,
    });

    const typingDuration = Math.ceil(cmd.command.length / TYPING_SPEED);
    frame += typingDuration + 12; // typing + pause after Enter

    // Output lines (instant)
    for (const out of cmd.output) {
      lines.push({
        text: out.text,
        color: out.color,
        bold: out.bold,
        appearFrame: frame,
      });
      frame += cmd.lineDelay;
    }

    frame += 22; // pause before next command
  }

  return lines;
}

const LINES = buildTimeline();
const LAST_FRAME = LINES[LINES.length - 1].appearFrame;
export const DURATION_IN_FRAMES = LAST_FRAME + 75; // hold final state

// ─── Components ──────────────────────────────────────────────────────

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
    <div
      style={{
        width: 12,
        height: 12,
        borderRadius: 6,
        backgroundColor: "#ff5f57",
      }}
    />
    <div
      style={{
        width: 12,
        height: 12,
        borderRadius: 6,
        backgroundColor: "#febc2e",
      }}
    />
    <div
      style={{
        width: 12,
        height: 12,
        borderRadius: 6,
        backgroundColor: "#28c840",
      }}
    />
    <span
      style={{
        marginLeft: 16,
        fontFamily: FONT,
        fontSize: 12,
        color: C.dim,
        letterSpacing: 0.3,
      }}
    >
      Terminal — motif
    </span>
  </div>
);

export const MotifDemo: React.FC = () => {
  const frame = useCurrentFrame();
  const cursorVisible = Math.floor(frame / 16) % 2 === 0;

  // Determine visible lines and their display text
  const visible: Array<{
    text: string;
    color: string;
    prefix?: string;
    prefixColor?: string;
    bold?: boolean;
    showCursor: boolean;
  }> = [];

  let activelyTyping = false;

  for (let i = 0; i < LINES.length; i++) {
    const line = LINES[i];
    if (frame < line.appearFrame) break;

    if (line.typed) {
      const elapsed = frame - line.appearFrame;
      const speed = line.typeSpeed ?? TYPING_SPEED;
      const charsToShow = Math.min(
        Math.floor(elapsed * speed),
        line.text.length,
      );
      const isTyping = charsToShow < line.text.length;

      visible.push({
        text: line.text.slice(0, charsToShow),
        color: line.color,
        prefix: line.prefix,
        prefixColor: line.prefixColor,
        bold: line.bold,
        showCursor: isTyping,
      });

      if (isTyping) {
        activelyTyping = true;
        break;
      }
    } else {
      visible.push({
        text: line.text,
        color: line.color,
        prefix: line.prefix,
        prefixColor: line.prefixColor,
        bold: line.bold,
        showCursor: false,
      });
    }
  }

  // Show a waiting prompt between commands when not actively typing
  if (!activelyTyping) {
    const nextTyped = LINES.find((l) => l.typed && frame < l.appearFrame);
    const showIdlePrompt = nextTyped || frame >= LAST_FRAME;
    if (showIdlePrompt) {
      visible.push({
        text: "",
        color: C.text,
        prefix: "$ ",
        prefixColor: C.green,
        showCursor: true,
      });
    }
  }

  // Scroll if too many lines
  const maxLines = 17;
  const scrollOffset = Math.max(0, visible.length - maxLines);
  const displayed = visible.slice(scrollOffset);

  // Fade in
  const opacity = interpolate(frame, [0, 12], [0, 1], {
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        backgroundColor: C.bg,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontFamily: FONT,
        opacity,
      }}
    >
      {/* Terminal window */}
      <div
        style={{
          width: 720,
          height: 430,
          borderRadius: 12,
          overflow: "hidden",
          border: `1px solid ${C.border}`,
          boxShadow:
            "0 20px 60px rgba(0, 0, 0, 0.5), 0 0 0 1px rgba(255,255,255,0.03)",
          display: "flex",
          flexDirection: "column",
        }}
      >
        <WindowChrome />

        {/* Terminal body */}
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
          {displayed.map((line, i) => (
            <div
              key={`${scrollOffset + i}`}
              style={{
                height: LINE_HEIGHT,
                whiteSpace: "pre",
                display: "flex",
              }}
            >
              {line.prefix && (
                <span style={{ color: line.prefixColor, fontWeight: 700 }}>
                  {line.prefix}
                </span>
              )}
              <span
                style={{
                  color: line.color,
                  fontWeight: line.bold ? 700 : 400,
                }}
              >
                {line.text}
              </span>
              {line.showCursor && cursorVisible && (
                <span style={{ color: C.cursor }}>█</span>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Subtle branding */}
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
            [LAST_FRAME, LAST_FRAME + 30],
            [0, 0.6],
            { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
          ),
        }}
      >
        pip install motif-cli
      </div>
    </AbsoluteFill>
  );
};
