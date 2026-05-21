import katex from "katex";

interface Props {
  text: string;
}

interface Segment {
  kind: "text" | "math";
  content: string;
  displayMode?: boolean;
}

const DELIMITERS = [
  { open: "$$", close: "$$", displayMode: true },
  { open: "\\[", close: "\\]", displayMode: true },
  { open: "\\(", close: "\\)", displayMode: false },
  { open: "$", close: "$", displayMode: false },
];

export default function LatexText({ text }: Props) {
  const segments = parseLatexSegments(text);
  return (
    <div className="latex-text">
      {segments.map((segment, index) => {
        if (segment.kind === "text") {
          return <span key={index}>{segment.content}</span>;
        }
        const rendered = katex.renderToString(segment.content, {
          displayMode: segment.displayMode,
          throwOnError: false,
          strict: "ignore",
          trust: false,
          output: "html",
        });
        const className = segment.displayMode ? "latex-math latex-display" : "latex-math";
        return <span key={index} className={className} dangerouslySetInnerHTML={{ __html: rendered }} />;
      })}
    </div>
  );
}

function parseLatexSegments(text: string): Segment[] {
  const segments: Segment[] = [];
  let cursor = 0;

  while (cursor < text.length) {
    const next = findNextDelimiter(text, cursor);
    if (!next) {
      segments.push({ kind: "text", content: text.slice(cursor) });
      break;
    }

    if (next.index > cursor) {
      segments.push({ kind: "text", content: text.slice(cursor, next.index) });
    }

    const contentStart = next.index + next.delimiter.open.length;
    const closeIndex = findClosingDelimiter(text, next.delimiter.close, contentStart);
    if (closeIndex === -1) {
      segments.push({ kind: "text", content: text.slice(next.index) });
      break;
    }

    segments.push({
      kind: "math",
      content: text.slice(contentStart, closeIndex),
      displayMode: next.delimiter.displayMode,
    });
    cursor = closeIndex + next.delimiter.close.length;
  }

  return segments;
}

function findNextDelimiter(text: string, start: number) {
  let best:
    | {
        index: number;
        delimiter: (typeof DELIMITERS)[number];
      }
    | null = null;

  for (const delimiter of DELIMITERS) {
    const index = text.indexOf(delimiter.open, start);
    if (index === -1 || isEscaped(text, index)) continue;
    if (delimiter.open === "$" && text[index + 1] === "$") continue;
    if (!best || index < best.index) {
      best = { index, delimiter };
    }
  }

  return best;
}

function findClosingDelimiter(text: string, close: string, start: number): number {
  let cursor = start;
  while (cursor < text.length) {
    const index = text.indexOf(close, cursor);
    if (index === -1) return -1;
    if (!isEscaped(text, index)) return index;
    cursor = index + close.length;
  }
  return -1;
}

function isEscaped(text: string, index: number): boolean {
  let slashCount = 0;
  for (let cursor = index - 1; cursor >= 0 && text[cursor] === "\\"; cursor -= 1) {
    slashCount += 1;
  }
  return slashCount % 2 === 1;
}

