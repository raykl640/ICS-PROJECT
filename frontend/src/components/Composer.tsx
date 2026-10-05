import { ArrowRight } from "lucide-react";
import { useState, type KeyboardEvent, type Ref } from "react";
import type { UiLanguage } from "../api/types";
import { Button } from "../design/components/Button";
import { TextArea } from "../design/components/Field";
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

  const submit = () => {
    if (canSubmit) onSubmit(value.trim(), language);
  };
  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      submit();
    }
  };

  return (
    <form
      aria-label={label}
      className="flex flex-col gap-4"
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      <TextArea
        ref={textareaRef}
        label={label}
        hint={t("submit_hint")}
        aside={
          <span className={cx(value.length >= MAX * 0.9 && "font-semibold text-accent")}>
            {t("char_count", { count: value.length, max: MAX })}
          </span>
        }
        value={value}
        maxLength={MAX}
        rows={compact ? 3 : 5}
        placeholder={t("question_placeholder")}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={onKeyDown}
        className="text-lg"
      />

      {examples && (
        <div>
          <p className="text-sm font-semibold text-ink-muted">{t("examples_label")}</p>
          <ul className="mt-2 flex flex-wrap gap-2">
            {EXAMPLES.map((key) => (
              <li key={key}>
                <Button className="h-auto rounded-lg text-left font-normal" onClick={() => onChange(t(key))}>
                  {t(key)}
                </Button>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex flex-col gap-1">
          <span aria-hidden="true" className="text-sm font-semibold text-ink-muted">
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
        <Button
          variant="primary"
          type="submit"
          disabled={!canSubmit}
          icon={<ArrowRight size={18} />}
          className="text-lg sm:min-w-32"
        >
          {t("submit")}
        </Button>
      </div>
      <p className="text-sm text-ink-muted">{t("disclaimer")}</p>
    </form>
  );
}
