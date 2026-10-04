import { type KeyboardEvent, type Ref, useState } from "react";
import type { UiLanguage } from "../api/types";
import { useI18n } from "../i18n";
import limits from "../limits.json";
import { BUTTON_PRIMARY } from "./buttons";

interface Props {
  busy: boolean;
  compact: boolean;
  onLanguage: (language: UiLanguage) => void;
  onSubmit: (question: string) => void;
  textareaRef: Ref<HTMLTextAreaElement>;
}

const MAX = limits.max_question_chars;
const EXAMPLES = ["example_1", "example_2", "example_3"] as const;
const LANGUAGES: UiLanguage[] = ["en", "sw"];

/** Question box with character counter, EN/SW choice, example chips and the always-visible disclaimer. */
export function QueryPanel({ busy, compact, onLanguage, onSubmit, textareaRef }: Props) {
  const { language, t } = useI18n();
  const [question, setQuestion] = useState("");
  const canSubmit = question.trim().length > 0 && !busy;

  const submit = () => {
    if (canSubmit) onSubmit(question.trim());
  };
  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      submit();
    }
  };

  return (
    <form
      aria-label={t("question_label")}
      className="rounded-2xl border border-line bg-surface p-4 shadow-sm sm:p-6"
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      <div className="flex flex-wrap items-end justify-between gap-3">
        <label htmlFor="question" className="font-serif text-xl font-semibold">
          {t("question_label")}
        </label>
        <fieldset className="flex items-center gap-2">
          <legend className="sr-only">{t("language_label")}</legend>
          <span aria-hidden="true" className="text-sm font-medium text-muted">
            {t("language_label")}
          </span>
          <div className="inline-flex rounded-lg border border-line bg-sunken p-1">
            {LANGUAGES.map((code) => (
              <label
                key={code}
                className="relative flex min-h-11 min-w-11 cursor-pointer items-center justify-center rounded-md px-3 text-sm font-semibold text-muted has-checked:bg-brand has-checked:text-on-brand has-focus-visible:outline-3 has-focus-visible:outline-offset-2 has-focus-visible:outline-(--focus)"
              >
                <input
                  type="radio"
                  name="language"
                  value={code}
                  checked={language === code}
                  onChange={() => onLanguage(code)}
                  className="sr-only"
                />
                <span aria-hidden="true">{code.toUpperCase()}</span>
                <span className="sr-only">{t(code === "en" ? "language_en" : "language_sw")}</span>
              </label>
            ))}
          </div>
        </fieldset>
      </div>

      <textarea
        id="question"
        ref={textareaRef}
        value={question}
        maxLength={MAX}
        rows={compact ? 3 : 5}
        placeholder={t("question_placeholder")}
        aria-describedby="question-count question-hint query-disclaimer"
        onChange={(event) => setQuestion(event.target.value)}
        onKeyDown={onKeyDown}
        className="mt-3 block w-full resize-y rounded-xl border border-line bg-paper px-4 py-3 text-lg leading-relaxed placeholder:text-muted focus:border-brand"
      />

      <div className="mt-2 flex flex-wrap items-center justify-between gap-x-4 gap-y-1 text-sm text-muted">
        <span id="question-count" className={question.length >= MAX * 0.9 ? "font-semibold text-accent" : undefined}>
          {t("char_count", { count: question.length, max: MAX })}
        </span>
        <span id="question-hint" className="hidden sm:inline">
          {t("submit_hint")}
        </span>
      </div>

      {!compact && (
        <div className="mt-4">
          <p className="text-sm font-semibold text-muted">{t("examples_label")}</p>
          <ul className="mt-2 flex flex-wrap gap-2">
            {EXAMPLES.map((key) => (
              <li key={key}>
                <button
                  type="button"
                  onClick={() => setQuestion(t(key))}
                  className="min-h-11 rounded-full border border-line bg-paper px-4 py-2 text-left text-base hover:border-brand hover:text-brand-strong"
                >
                  {t(key)}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="mt-5 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <p id="query-disclaimer" className="max-w-prose text-sm leading-snug text-muted">
          {t("disclaimer")}
        </p>
        <button type="submit" disabled={!canSubmit} className={BUTTON_PRIMARY + " shrink-0 text-lg sm:min-w-32"}>
          {t("submit")}
        </button>
      </div>
    </form>
  );
}
