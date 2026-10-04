// Finds "Section 41(2)", "s. 45", "ss. 41 and 45", "Article 41" in the answer and maps each number to a retrieved chunk,
// mirroring the backend check (backend/app/generation/citations.py): an Act named next to the citation binds it,
// otherwise any source with that unit and number matches.
import type { SourceChunk } from "../api/types";

export interface CitationSpan {
  start: number;
  end: number;
  chunkId: string;
}

const NUM = String.raw`\d+[A-Z]?(?:\s*\(\w{1,4}\))*`;
const CITATION = new RegExp(
  String.raw`\b(sections?|ss?\.|articles?|arts?\.)\s*(${NUM}(?:\s*(?:,|and|or|&)\s*${NUM})*)`,
  "gi",
);
const NUMBER = new RegExp(`(\\d+[A-Z]?)(?:\\s*\\(\\w{1,4}\\))*`, "gi");
const LOOKBACK = 100;
const AFTER = /^\s*(?:of|in|under)\s+(?:the\s+)?/i;

/** Names an Act may be written as: its title, and without a trailing "of Kenya". */
function aliases(act: string): string[] {
  const short = act.replace(/\s+of\s+Kenya$/i, "");
  return short === act ? [act] : [act, short];
}

/** The Act named nearest before the citation (within LOOKBACK chars), else one named right after it ("of the X Act"). */
function boundAct(text: string, start: number, end: number, acts: string[]): string | null {
  const before = text.slice(Math.max(0, start - LOOKBACK), start).toLowerCase();
  let best: { act: string; at: number } | null = null;
  for (const act of acts) {
    for (const name of aliases(act)) {
      const at = before.lastIndexOf(name.toLowerCase());
      if (at >= 0 && (!best || at > best.at)) best = { act, at };
    }
  }
  if (best) return best.act;
  const after = AFTER.exec(text.slice(end));
  if (!after) return null;
  const rest = text.slice(end + after[0].length).toLowerCase();
  return acts.find((act) => aliases(act).some((name) => rest.startsWith(name.toLowerCase()))) ?? null;
}

/** Citation spans in text that resolve to one of the sources (first in rank order wins). */
export function findCitations(text: string, sources: SourceChunk[]): CitationSpan[] {
  const acts = [...new Set(sources.map((s) => s.act))];
  const spans: CitationSpan[] = [];
  for (const match of text.matchAll(CITATION)) {
    const start = match.index;
    const end = start + match[0].length;
    const unit = /^art/i.test(match[1]) ? "article" : "section";
    const act = boundAct(text, start, end, acts);
    const listStart = end - match[2].length;
    for (const number of match[2].matchAll(NUMBER)) {
      const target = sources.find(
        (s) =>
          s.unit_type === unit &&
          s.section_num.toUpperCase() === number[1].toUpperCase() &&
          (act === null || s.act === act),
      );
      if (!target) continue;
      const numberStart = listStart + number.index;
      spans.push({
        start: number.index === 0 ? start : numberStart,
        end: numberStart + number[0].length,
        chunkId: target.chunk_id,
      });
    }
  }
  return spans;
}
