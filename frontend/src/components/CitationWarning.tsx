import { useI18n } from "../i18n";
import { Banner } from "./Banner";

/** Shown when the answer cites provisions that were not among the retrieved sources. */
export function CitationWarning({ unmatched }: { unmatched: string[] }) {
  const { t } = useI18n();
  if (!unmatched.length) return null;
  return (
    <Banner tone="warn" title={t("citation_warning")}>
      <p className="mt-1">
        {t("citation_unmatched")} <span className="font-medium">{unmatched.join(", ")}</span>
      </p>
    </Banner>
  );
}
