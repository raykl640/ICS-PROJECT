import { cx } from "../design/cx";
import { type StringKey, useI18n } from "../i18n";
import { type Strength, strength } from "../lib/password";
import limits from "../limits.json";

const LEVELS: Strength[] = ["short", "fair", "good", "strong"];
const LABELS: Record<Strength, StringKey> = {
  short: "strength_short",
  fair: "strength_fair",
  good: "strength_good",
  strong: "strength_strong",
};
const TONES: Record<Strength, string> = {
  short: "bg-danger",
  fair: "bg-warn",
  good: "bg-success",
  strong: "bg-success",
};

/** Length-based strength bar with its level in words (colour is never the only signal). */
export function StrengthMeter({ password }: { password: string }) {
  const { t } = useI18n();
  const level = strength(password, limits.password_min_chars);
  const index = LEVELS.indexOf(level);
  return (
    <div className="flex items-center gap-3" aria-live="polite">
      <div
        role="meter"
        aria-label={t("strength_label")}
        aria-valuemin={0}
        aria-valuemax={LEVELS.length - 1}
        aria-valuenow={index}
        aria-valuetext={t(LABELS[level])}
        className="flex flex-1 gap-1"
      >
        {LEVELS.map((name, i) => (
          <span
            key={name}
            className={cx("h-1.5 flex-1 rounded-full", password && i <= index ? TONES[level] : "bg-sunken")}
          />
        ))}
      </div>
      <span className="w-24 text-sm font-semibold text-ink-muted">{password ? t(LABELS[level]) : ""}</span>
    </div>
  );
}
