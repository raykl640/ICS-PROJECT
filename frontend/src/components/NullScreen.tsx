import type { NullPayload } from "../api/types";
import { useI18n } from "../i18n";
import { BUTTON_SECONDARY } from "./buttons";
import { ReferralFooter } from "./ReferralFooter";

/** The fixed fallback when too little relevant law was found: no answer is generated. */
export function NullScreen({ info, onAskAgain }: { info: NullPayload; onAskAgain: () => void }) {
  const { t } = useI18n();
  return (
    <section aria-labelledby="null-title" className="space-y-5">
      <div className="rounded-xl border border-line bg-surface p-6 sm:p-8">
        <p aria-hidden="true" className="font-serif text-5xl leading-none text-brand">
          §
        </p>
        <h2 id="null-title" className="mt-3 font-serif text-2xl font-semibold sm:text-3xl">
          {t("null_title")}
        </h2>
        <p className="mt-3 text-lg leading-relaxed">{info.message}</p>
        <p className="mt-4 text-base text-muted">{info.disclaimer}</p>
        <button type="button" onClick={onAskAgain} className={BUTTON_SECONDARY + " mt-6"}>
          {t("ask_again")}
        </button>
      </div>
      <ReferralFooter />
    </section>
  );
}
