import { PageTitle } from "../app/PageTitle";
import { Card } from "../design/components/Display";
import { type StringKey, useI18n } from "../i18n";

// Mirrors docs/LIMITATIONS.md in plain words; no claims beyond it.
const STEPS: StringKey[] = ["how_step_1", "how_step_2", "how_step_3", "how_step_4"];
const LIMITS: StringKey[] = ["how_limit_1", "how_limit_2", "how_limit_3", "how_limit_4", "how_limit_5"];
const ACTS: StringKey[] = [
  "act_constitution",
  "act_employment",
  "act_shops",
  "act_rent",
  "act_land",
  "act_consumer",
  "act_police",
  "act_cpc",
  "act_traffic",
  "act_legal_aid",
  "act_labour",
  "act_penal",
  "act_evidence",
  "act_civil_procedure",
  "act_small_claims",
  "act_limitation",
  "act_land_registration",
  "act_marriage",
  "act_matrimonial",
  "act_succession",
  "act_trafficking",
  "act_refugees",
  "act_public_health",
  "act_mental_health",
  "act_hiv",
];

/** A plain explanation of how answers are made, what is covered, the limits and privacy. */
export function HowItWorks() {
  const { t } = useI18n();
  return (
    <div className="flex max-w-3xl flex-col gap-6">
      <div>
        <PageTitle>{t("how_title")}</PageTitle>
        <p className="mt-3 text-lg text-ink">{t("how_intro")}</p>
      </div>
      <Card title={t("how_steps_title")}>
        <ol className="flex flex-col gap-3">
          {STEPS.map((key, index) => (
            <li key={key} className="flex gap-3 text-ink">
              <span
                aria-hidden="true"
                className="grid size-7 shrink-0 place-items-center rounded-full bg-sunken text-sm font-semibold text-ink"
              >
                {index + 1}
              </span>
              <span>{t(key)}</span>
            </li>
          ))}
        </ol>
      </Card>
      <Card title={t("how_covers_title")}>
        <ul className="grid gap-x-6 gap-y-1 text-ink sm:grid-cols-2">
          {ACTS.map((key) => (
            <li key={key}>{t(key)}</li>
          ))}
        </ul>
        <p className="mt-3 text-ink-muted">{t("how_covers_body")}</p>
      </Card>
      <Card title={t("how_limits_title")}>
        <ul className="ml-5 flex list-disc flex-col gap-2 text-ink">
          {LIMITS.map((key) => (
            <li key={key}>{t(key)}</li>
          ))}
        </ul>
      </Card>
      <Card title={t("how_privacy_title")}>
        <p className="text-ink">{t("how_privacy_body")}</p>
      </Card>
    </div>
  );
}
