import type { UiLanguage } from "../api/types";
import referralFile from "../../../config/referral_resources.json";
import { useI18n } from "../i18n";

export interface Referral {
  name: string;
  description?: Partial<Record<UiLanguage, string>>;
  contact?: string;
  verified: boolean;
}

const FILE_ENTRIES = (referralFile as { entries: Referral[] }).entries;

/** Help organisations from config/referral_resources.json; only human-verified entries; nothing if there are none. */
export function ReferralFooter({ entries = FILE_ENTRIES }: { entries?: Referral[] }) {
  const { language, t } = useI18n();
  const verified = entries.filter((entry) => entry.verified === true);
  if (!verified.length) return null;
  return (
    <section aria-labelledby="referral-title" className="border-t-[3px] border-ink pt-4">
      <h2 id="referral-title" className="font-display-style text-2xl text-ink">
        {t("referral_title")}
      </h2>
      <ul className="mt-3 flex flex-col gap-3">
        {verified.map((entry) => (
          <li key={entry.name}>
            <p className="font-semibold text-ink">{entry.name}</p>
            {entry.description?.[language] && <p className="text-ink-muted">{entry.description[language]}</p>}
            {entry.contact && <p className="font-semibold text-brand">{entry.contact}</p>}
          </li>
        ))}
      </ul>
    </section>
  );
}
