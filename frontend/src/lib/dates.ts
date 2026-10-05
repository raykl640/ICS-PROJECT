// Dates shown in the library: the stored UTC time in the reader's local time zone.
import type { UiLanguage } from "../api/types";

const LOCALES: Record<UiLanguage, string> = { en: "en-KE", sw: "sw-KE" };

/** "5 Oct 2026, 14:03" style date and time. */
export function formatDateTime(iso: string, language: UiLanguage): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return new Intl.DateTimeFormat(LOCALES[language], { dateStyle: "medium", timeStyle: "short" }).format(date);
}

/** Today as a long date for letters, e.g. "5 October 2026". */
export function formatLetterDate(date: Date, language: UiLanguage): string {
  return new Intl.DateTimeFormat(LOCALES[language], { day: "numeric", month: "long", year: "numeric" }).format(date);
}
