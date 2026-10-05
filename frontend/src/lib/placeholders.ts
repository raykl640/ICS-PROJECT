// Letter placeholders such as "[Your Name]" or "[Date]": find them (to highlight) and fill the ones the letter
// profile can answer, returning the changes so the user sees a preview before anything is applied.
import type { Profile } from "../api/accounts";

const PLACEHOLDER = /\[([^[\]\n]{1,40})\]/g;

export type ProfileField = keyof Profile;
type FillKey = ProfileField | "date";

// Normalised placeholder label -> what fills it (labels lower-cased, "your"/"my" and punctuation removed).
const KEYS: Record<string, FillKey> = {
  name: "name",
  "full name": "name",
  address: "address",
  "postal address": "address",
  phone: "phone",
  "phone number": "phone",
  telephone: "phone",
  "telephone number": "phone",
  email: "email",
  "email address": "email",
  "id number": "id_number",
  "id no": "id_number",
  "national id": "id_number",
  "national id number": "id_number",
  date: "date",
  "todays date": "date",
};

export interface Segment {
  text: string;
  placeholder: boolean;
}

export interface Fill {
  placeholder: string;
  value: string;
  count: number;
}

export interface FillResult {
  text: string;
  changes: Fill[];
  /** Placeholders left as they are (no matching profile field, or the field is empty). */
  missing: string[];
}

/** "[Your Name]" -> "name". */
export function normaliseLabel(label: string): string {
  return label
    .toLowerCase()
    .replace(/[^a-z0-9 ]/g, "")
    .replace(/\b(your|my)\b/g, " ")
    .split(/\s+/)
    .filter(Boolean)
    .join(" ");
}

/** The text cut into plain runs and placeholder runs (for highlighting). */
export function segments(text: string): Segment[] {
  const parts: Segment[] = [];
  let last = 0;
  for (const match of text.matchAll(PLACEHOLDER)) {
    const start = match.index;
    if (start > last) parts.push({ text: text.slice(last, start), placeholder: false });
    parts.push({ text: match[0], placeholder: true });
    last = start + match[0].length;
  }
  if (last < text.length) parts.push({ text: text.slice(last), placeholder: false });
  return parts;
}

/** Distinct placeholders in order of first appearance. */
export function placeholders(text: string): string[] {
  return [
    ...new Set(
      segments(text)
        .filter((s) => s.placeholder)
        .map((s) => s.text),
    ),
  ];
}

/** Fill the placeholders the profile (and today's date) can answer; nothing else in the text changes. */
export function fillFromProfile(text: string, profile: Profile, today: string): FillResult {
  const values = { ...profile, date: today };
  const changes = new Map<string, Fill>();
  const missing = new Set<string>();
  const filled = text.replace(PLACEHOLDER, (whole: string, label: string) => {
    const key = KEYS[normaliseLabel(label)];
    const value = key ? values[key].trim() : "";
    if (!value) {
      missing.add(whole);
      return whole;
    }
    const change = changes.get(whole) ?? { placeholder: whole, value, count: 0 };
    change.count += 1;
    changes.set(whole, change);
    return value;
  });
  return { text: filled, changes: [...changes.values()], missing: [...missing] };
}
