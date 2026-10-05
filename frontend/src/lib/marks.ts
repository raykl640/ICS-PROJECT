// Search snippets: split text into plain and marked parts from [start, end) code-point offsets (never HTML).

export interface Segment {
  text: string;
  mark: boolean;
}

/** Plain/marked segments; overlapping or out-of-range marks are skipped, so any input renders safely. */
export function markSegments(text: string, marks: readonly (readonly [number, number])[]): Segment[] {
  const chars = Array.from(text);
  const out: Segment[] = [];
  let pos = 0;
  for (const [start, end] of [...marks].sort((a, b) => a[0] - b[0])) {
    if (start < pos || end <= start || end > chars.length) continue;
    if (start > pos) out.push({ text: chars.slice(pos, start).join(""), mark: false });
    out.push({ text: chars.slice(start, end).join(""), mark: true });
    pos = end;
  }
  if (pos < chars.length) out.push({ text: chars.slice(pos).join(""), mark: false });
  return out;
}
