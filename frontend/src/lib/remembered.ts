// Usernames the user chose to remember on this device (localStorage; usernames only, never passwords).
const KEY = "hakiai.usernames";
const MAX = 5;

/** Remembered usernames, most recent first. */
export function rememberedUsernames(): string[] {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(KEY) ?? "[]");
    return Array.isArray(value) ? value.filter((v): v is string => typeof v === "string").slice(0, MAX) : [];
  } catch {
    return [];
  }
}

function save(names: string[]): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(names.slice(0, MAX)));
  } catch {
    // Storage blocked: nothing is remembered.
  }
}

/** Put a username first in the list. */
export const rememberUsername = (name: string): void =>
  save([name, ...rememberedUsernames().filter((n) => n !== name)]);

/** Drop a username from the list. */
export const forgetUsername = (name: string): void => save(rememberedUsernames().filter((n) => n !== name));
