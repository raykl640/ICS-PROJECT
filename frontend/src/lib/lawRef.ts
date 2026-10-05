// Command palette parsing of law references: "Employment s.41", "s 41 employment", "art 27", "rent act".
import type { ActInfo } from "../api/laws";

export interface LawTarget {
  slug: string;
  /** Set when the query names a section/article number. */
  chunkId?: string;
  label: string;
}

const UNIT = /\b(s|sec|sect|section|art|article)\b\.?\s*(\d+[a-z]?)\b/i;
const NUMBER = /\b(\d+[a-z]?)\b/i;
const IGNORED = new Set(["of", "the", "act", "and", "cap"]);

const words = (text: string) =>
  text
    .toLowerCase()
    .split(/[^\p{L}\p{N}]+/u)
    .filter((w) => w.length > 1 && !IGNORED.has(w));

/** Acts whose name has a word starting with each query word. */
function actsNamed(queryWords: string[], acts: ActInfo[]): ActInfo[] {
  if (!queryWords.length) return [];
  return acts.filter((act) => {
    const nameWords = words(act.name);
    return queryWords.every((q) => nameWords.some((w) => w.startsWith(q)));
  });
}

/** Acts and sections a palette query points at (best first); [] when it names no Act and no unit. */
export function parseLawQuery(query: string, acts: ActInfo[]): LawTarget[] {
  const unitMatch = UNIT.exec(query);
  const numberMatch = unitMatch ? null : NUMBER.exec(query);
  const num = (unitMatch?.[2] ?? numberMatch?.[1])?.toLowerCase();
  const unitWord = unitMatch?.[1].toLowerCase();
  const wantArticle = unitWord?.startsWith("a") ?? false;
  const rest = (unitMatch ?? numberMatch) ? query.replace((unitMatch ?? numberMatch)![0], " ") : query;
  let named = actsNamed(words(rest), acts);
  if (!named.length && unitWord) named = acts.filter((act) => (act.unit === "Article") === wantArticle);
  return named
    .filter((act) => !unitWord || (act.unit === "Article") === wantArticle)
    .map((act) => {
      if (!num) return { slug: act.slug, label: act.name };
      const unit = act.unit === "Article" ? "Article" : "section";
      return { slug: act.slug, chunkId: `${act.slug}-${num}`, label: `${act.name}, ${unit} ${num}` };
    });
}
