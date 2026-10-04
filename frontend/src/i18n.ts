// EN/SW interface strings, shared with the backend (backend/app/lang/ui_strings.json; Kiswahili needs human review).
import { createContext, useContext } from "react";
import uiStrings from "../../backend/app/lang/ui_strings.json";
import type { UiLanguage } from "./api/types";

export type StringKey = keyof typeof uiStrings.en;
export type Translate = (key: StringKey, vars?: Record<string, string | number>) => string;

/** A translate function for one language; "{name}" placeholders are filled from vars. */
export function makeTranslate(language: UiLanguage): Translate {
  const strings: Record<StringKey, string> = uiStrings[language];
  return (key, vars) => strings[key].replace(/\{(\w+)\}/g, (whole, name: string) => String(vars?.[name] ?? whole));
}

export const I18nContext = createContext<{ language: UiLanguage; t: Translate }>({
  language: "en",
  t: makeTranslate("en"),
});

/** The active language and its translate function. */
export const useI18n = () => useContext(I18nContext);
