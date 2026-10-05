import { ArrowRight, ArrowUpRight } from "lucide-react";
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

/** Question box: character counter, answer language, Ctrl/Cmd+Enter, examples and the disclaimer. */
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

  const nearLimit = value.length >= MAX * 0.9;

  return (
    <form
      aria-label={label}
      className={cx("flex flex-col", compact ? "gap-2" : "gap-4")}
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      {/* The question sheet: a label strip, ruled writing lines, and a strip with the language and the Ask key. */}
      <div className="border-2 border-ink bg-raised">
        <div className="flex items-baseline justify-between gap-3 bg-ink px-4 py-2 text-canvas">
          <label htmlFor={fieldId} className="label-mono font-semibold">
            {label}
          </label>
          <span className={cx("font-mono text-xs", nearLimit && "font-semibold text-highlight")}>
            {t("char_count", { count: value.length, max: MAX })}
          </span>
        </div>
        <textarea
          ref={textareaRef}
          id={fieldId}
          aria-describedby={hintId}
          value={value}
          maxLength={MAX}
          rows={compact ? 2 : 4}
          placeholder={t("question_placeholder")}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={onKeyDown}
          className="ruled block w-full resize-y bg-transparent px-4 pt-1 pb-1 font-reading text-xl text-ink placeholder:text-ink-muted"
        />
        <div className="flex flex-wrap items-center justify-between gap-3 border-t-2 border-ink px-3 py-2.5">
          <div className="flex items-center gap-3">
            <span aria-hidden="true" className="label-mono text-ink-muted">
              {t("answer_language")}
            </span>
            <ToggleGroup
              label={t("answer_language")}
              value={language}
              onValueChange={setLanguage}
              items={[
                { value: "en", label: t("language_en") },
                { value: "sw", label: t("language_sw") },
              ]}
            />
          </div>
          <div className="flex w-full items-center gap-3 sm:w-auto">
            <span id={hintId} className="hidden font-mono text-xs text-ink-muted sm:inline">
              {t("submit_hint")}
            </span>
            <Button
              variant="primary"
              type="submit"
              disabled={!canSubmit}
              icon={<ArrowRight size={18} />}
              className="min-w-28 flex-1 text-lg sm:flex-none"
            >
              {t("submit")}
            </Button>
          </div>
        </div>
      </div>

      {examples && (
        <div>
          <p className="label-mono text-ink-muted">{t("examples_label")}</p>
          <ul className="mt-2 flex flex-col border-t border-line-subtle">
            {EXAMPLES.map((key, index) => (
              <li key={key} className="border-b border-line-subtle">
                <button
                  type="button"
                  onClick={() => onChange(t(key))}
                  className="group target flex w-full cursor-pointer items-baseline gap-3 px-1 py-2.5 text-left motion-colors hover:bg-highlight"
                >
                  <span aria-hidden="true" className="font-mono text-xs text-ink-muted">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <span className="flex-1 font-reading text-lg">{t(key)}</span>
                  <ArrowUpRight
                    aria-hidden="true"
                    size={18}
                    className="shrink-0 self-center text-ink-muted motion-colors group-hover:text-ink"
                  />
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {!compact && <p className="max-w-prose text-sm text-ink-muted">{t("disclaimer")}</p>}
    </form>
  );
}
