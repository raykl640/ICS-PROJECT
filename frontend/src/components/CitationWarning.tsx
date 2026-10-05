import { Notice } from "../design/components/Display";
import { useI18n } from "../i18n";

/** Shown when the answer cites provisions that were not among the retrieved sources. */
export function CitationWarning({ unmatched }: { unmatched: string[] }) {
  const { t } = useI18n();
  if (!unmatched.length) return null;
  return (
    <Notice tone="warn" title={t("citation_warning")}>
      <p className="mt-1">
        {t("citation_unmatched")} <span className="font-semibold">{unmatched.join(", ")}</span>
      </p>
    </Notice>
  );
}
