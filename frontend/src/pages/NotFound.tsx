import { Home } from "lucide-react";
import { Link } from "react-router";
import { PageTitle } from "../app/PageTitle";
import { useI18n } from "../i18n";

/** Unknown address. */
export function NotFound() {
  const { t } = useI18n();
  return (
    <div className="flex max-w-xl flex-col items-start gap-4">
      <PageTitle>{t("not_found_title")}</PageTitle>
      <p className="text-lg text-ink">{t("not_found_body")}</p>
      <Link
        to="/"
        className="target inline-flex items-center gap-2 rounded-sm border-2 border-brand bg-brand px-4 py-2 font-semibold text-brand-ink shadow-[0_3px_0_var(--hk-ink)] motion-colors hover:border-ink hover:bg-ink hover:text-canvas"
      >
        <Home aria-hidden="true" size={18} />
        {t("go_home")}
      </Link>
    </div>
  );
}
