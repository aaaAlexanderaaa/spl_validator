import type { Position } from "./tokens.js";

export function posFromOffset(text: string, offset: number): Position {
  let line = 1;
  let lastNl = -1;
  for (let i = 0; i < offset && i < text.length; i++) {
    if (text[i] === "\n") {
      line += 1;
      lastNl = i;
    }
  }
  const col = offset - lastNl;
  return { line, column: col, offset };
}

function scanDoubleQuotedStringEnd(text: string, startInside: number): number | null {
  let i = startInside;
  const n = text.length;
  while (i < n) {
    const ch = text[i]!;
    if (ch === "\\" && i + 1 < n) {
      i += 2;
      continue;
    }
    if (ch === '"') return i + 1;
    i += 1;
  }
  return null;
}

function mapSearchOpenQuoteAt(text: string, k: number): number | null {
  const n = text.length;
  if (k + 6 > n || text.slice(k, k + 6).toLowerCase() !== "search") return null;
  if (k > 0 && /[a-z0-9_]/i.test(text[k - 1]!)) return null;
  if (k + 6 < n && /[a-z0-9_]/i.test(text[k + 6]!)) return null;
  let m = k + 6;
  while (m < n && /\s/.test(text[m]!)) m += 1;
  if (m >= n || text[m] !== "=") return null;
  m += 1;
  while (m < n && /\s/.test(text[m]!)) m += 1;
  if (m >= n || text[m] !== '"') return null;
  return m;
}

function* iterMapBodyStarts(text: string): Generator<number> {
  const n = text.length;
  let j = 0;
  while (j < n && /\s/.test(text[j]!)) j += 1;
  if (j + 3 <= n && text.slice(j, j + 3).toLowerCase() === "map") {
    if (j + 3 >= n || !/[a-z0-9_]/i.test(text[j + 3]!)) yield j + 3;
  }
  for (let i = 0; i < n; i++) {
    if (text[i] === "|") {
      let jj = i + 1;
      while (jj < n && /\s/.test(text[jj]!)) jj += 1;
      if (jj + 3 <= n && text.slice(jj, jj + 3).toLowerCase() === "map") {
        if (jj + 3 >= n || !/[a-z0-9_]/i.test(text[jj + 3]!)) yield jj + 3;
      }
    }
  }
}

function findMapSearchPayloadSpans(text: string): [Array<[number, number]>, boolean] {
  const spans: Array<[number, number]> = [];
  const n = text.length;
  for (const bodyStart of iterMapBodyStarts(text)) {
    let k = bodyStart;
    while (k < n) {
      if (text[k] === "|") break;
      const oq = mapSearchOpenQuoteAt(text, k);
      if (oq !== null) {
        const inside = oq + 1;
        const endEx = scanDoubleQuotedStringEnd(text, inside);
        if (endEx === null) return [[], true];
        if (inside < endEx - 1) spans.push([inside, endEx - 1]);
        k = endEx;
        continue;
      }
      k += 1;
    }
  }
  return [spans, false];
}

export function maskMapSearchStringPayloads(
  text: string,
): [string, Array<[number, number]>, boolean] {
  const [spans, aborted] = findMapSearchPayloadSpans(text);
  if (aborted || spans.length === 0) return [text, spans, aborted];
  const out = [...text];
  for (const [a, b] of spans) {
    for (let p = a; p < b; p++) {
      out[p] = " ";
    }
  }
  return [out.join(""), spans, false];
}

export function maskMarkdownTripleBackticks(
  text: string,
): [string, Array<[number, number]>, boolean] {
  const spans: Array<[number, number]> = [];
  const out = [...text];
  let i = 0;
  let unclosed = false;
  while (true) {
    const start = text.indexOf("```", i);
    if (start < 0) break;
    const end = text.indexOf("```", start + 3);
    if (end < 0) {
      unclosed = true;
      break;
    }
    const endFull = end + 3;
    spans.push([start, endFull]);
    for (let j = start; j < endFull; j++) {
      if (out[j] !== "\n") out[j] = " ";
    }
    i = endFull;
  }
  return [out.join(""), spans, unclosed];
}
