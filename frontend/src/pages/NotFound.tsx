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
        className="target inline-flex items-center gap-2 rounded-md border border-brand bg-brand px-4 py-2 font-semibold text-brand-ink motion-colors hover:brightness-110"
      >
        <Home aria-hidden="true" size={18} />
        {t("go_home")}
      </Link>
    </div>
  );
}
