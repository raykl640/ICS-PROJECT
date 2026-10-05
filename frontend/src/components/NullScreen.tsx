import { SearchX } from "lucide-react";
import type { NullPayload } from "../api/types";
import { Button } from "../design/components/Button";
import { useI18n } from "../i18n";
import { ReferralFooter } from "./ReferralFooter";

/** The fixed fallback when too little relevant law was found: no answer is generated. */
export function NullScreen({ info, onAskAgain }: { info: NullPayload; onAskAgain: () => void }) {
  const { t } = useI18n();
  return (
    <section aria-labelledby="null-title" className="flex flex-col gap-5">
      <div className="border-2 border-ink bg-surface p-6 sm:p-8">
        <SearchX aria-hidden="true" size={32} className="text-accent" />
        <h2 id="null-title" className="mt-3 font-display-style text-3xl text-ink sm:text-4xl">
          {t("null_title")}
        </h2>
        <p className="mt-3 max-w-[60ch] font-reading text-xl leading-relaxed text-ink">{info.message}</p>
        <p className="mt-4 text-ink-muted">{info.disclaimer}</p>
        <Button className="mt-6" onClick={onAskAgain}>
          {t("ask_again")}
        </Button>
      </div>
      <ReferralFooter />
    </section>
  );
}
