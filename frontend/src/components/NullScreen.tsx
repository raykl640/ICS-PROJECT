import { SearchX } from "lucide-react";
import { Link } from "react-router";
import type { NullPayload } from "../api/types";
import { useI18n } from "../i18n";
import { ReferralFooter } from "./ReferralFooter";

/** The fixed fallback when too little relevant law was found: no answer is generated. */
export function NullScreen({ info }: { info: NullPayload }) {
  const { t } = useI18n();
  return (
    <section aria-labelledby="null-title" className="flex flex-col gap-5">
      <div className="rounded-lg bg-sunken p-6 sm:p-8">
        <SearchX aria-hidden="true" size={28} className="text-ink-muted" />
        <h2 id="null-title" className="mt-3 font-display-style text-2xl text-ink">
          {t("null_title")}
        </h2>
        <p className="mt-3 max-w-[60ch] font-reading text-xl leading-relaxed text-ink">{info.message}</p>
        <p className="mt-4 text-ink-muted">{info.disclaimer}</p>
        <Link to="/laws" className="mt-4 inline-block font-semibold text-brand underline-offset-3 hover:underline">
          {t("home_browse")}
        </Link>
      </div>
      <ReferralFooter />
    </section>
  );
}
