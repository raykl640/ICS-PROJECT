import { ArrowUp } from "lucide-react";
import { useId, useState, type KeyboardEvent, type Ref } from "react";
import type { UiLanguage } from "../api/types";
import { Button } from "../design/components/Button";
import { ToggleGroup } from "../design/components/ToggleGroup";
import { cx } from "../design/cx";
import { useI18n } from "../i18n";
import limits from "../limits.json";

const MAX = limits.max_question_chars;
const EXAMPLES = ["example_1", "example_2", "example_3"] as const;

interface ComposerProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  onSubmit: (question: string, language: UiLanguage) => void;
  /** An answer is on its way: typing is allowed, sending is not. */
  busy: boolean;
  /** Offer example questions that fill the box. */
  examples?: boolean;
  compact?: boolean;
  textareaRef?: Ref<HTMLTextAreaElement>;
}

/** Question box: answer language, Ctrl/Cmd+Enter, a counter near the limit, examples and the disclaimer. */
export function Composer({ label, value, onChange, onSubmit, busy, examples, compact, textareaRef }: ComposerProps) {
  const { language: uiLanguage, t } = useI18n();
  const [language, setLanguage] = useState<UiLanguage>(uiLanguage);
  const canSubmit = value.trim().length > 0 && !busy;
  const fieldId = useId();
  const hintId = `${fieldId}-hint`;

  const submit = () => {
    if (canSubmit) onSubmit(value.trim(), language);
  };
  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      submit();
    }
  };

  const nearLimit = value.length >= MAX * 0.8;

  return (
    <form
      aria-label={label}
      className={cx("flex flex-col", compact ? "gap-2" : "gap-5")}
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      <div className="rounded-lg border border-line bg-raised shadow-raised motion-colors focus-within:border-brand">
        <label htmlFor={fieldId} className="sr-only">
          {label}
        </label>
        <textarea
          ref={textareaRef}
          id={fieldId}
          aria-describedby={hintId}
          value={value}
          maxLength={MAX}
          rows={compact ? 1 : 3}
          placeholder={compact ? label : t("question_placeholder")}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={onKeyDown}
          className={cx(
            "block w-full resize-none rounded-t-lg bg-transparent px-4 pt-3.5 text-ink outline-none placeholder:text-ink-muted",
            compact ? "text-base" : "font-reading text-lg leading-relaxed",
          )}
        />
        <div className="flex items-center justify-between gap-2 px-2 pt-1 pb-2">
          <div className="flex min-w-0 items-center gap-2 sm:pl-2">
            <span aria-hidden="true" className="hidden text-sm text-ink-muted sm:inline">
              {t("answer_language")}
            </span>
            <ToggleGroup
              label={t("answer_language")}
              value={language}
              onValueChange={setLanguage}
              className="text-sm"
              items={[
                { value: "en", label: t("language_en") },
                { value: "sw", label: t("language_sw") },
              ]}
            />
          </div>
          <div className="ml-auto flex shrink-0 items-center gap-3">
            {nearLimit && (
              <span className="text-xs font-semibold text-warn">
                {t("char_count", { count: value.length, max: MAX })}
              </span>
            )}
            <span id={hintId} className="sr-only">
              {t("submit_hint")}
            </span>
            <Button variant="primary" type="submit" disabled={!canSubmit} icon={<ArrowUp size={18} />}>
              {t("submit")}
            </Button>
          </div>
        </div>
      </div>

      {examples && (
        <div className="flex flex-col gap-2">
          <p className="text-sm text-ink-muted">{t("examples_label")}</p>
          <ul className="flex flex-wrap gap-2">
            {EXAMPLES.map((key) => (
              <li key={key}>
                <button
                  type="button"
                  onClick={() => onChange(t(key))}
                  className="target cursor-pointer rounded-full border border-line-subtle bg-raised px-3.5 py-2 text-left text-sm text-ink motion-colors hover:border-line hover:bg-sunken"
                >
                  {t(key)}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {!compact && <p className="max-w-prose text-xs text-ink-muted">{t("disclaimer")}</p>}
    </form>
  );
}
