// Length-based password strength (no word lists, nothing leaves the browser): length is what resists guessing offline.
export type Strength = "short" | "fair" | "good" | "strong";

/** Strength band for a password given the minimum length the server enforces. */
export function strength(password: string, min: number): Strength {
  const length = [...password].length;
  if (length < min) return "short";
  if (length < min + 4) return "fair";
  if (length < min + 10) return "good";
  return "strong";
}
