import { render } from "@testing-library/react";
import type { ReactElement, ReactNode } from "react";
import type { UiLanguage } from "../api/types";
import { I18nContext, makeTranslate } from "../i18n";

/** Render inside the i18n context for a language (kept across rerender). */
export function renderIn(ui: ReactElement, language: UiLanguage = "en") {
  const wrapper = ({ children }: { children: ReactNode }) => (
    <I18nContext.Provider value={{ language, t: makeTranslate(language) }}>{children}</I18nContext.Provider>
  );
  return render(ui, { wrapper });
}
