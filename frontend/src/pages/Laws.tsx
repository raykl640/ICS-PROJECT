import { BookOpen } from "lucide-react";
import { Link } from "react-router";
import { listActs } from "../api/laws";
import { PageTitle } from "../app/PageTitle";
import { LawSearchForm } from "../components/laws/LawSearchForm";
import { Skeleton } from "../design/components/Display";
import { useLoad } from "../hooks/useLoad";
import { useI18n } from "../i18n";

/** The Acts in the corpus, each opening its table of contents. */
export function Laws() {
  const { t } = useI18n();
  const { result } = useLoad("acts", listActs);
  return (
    <div className="flex flex-col gap-6">
      <div>
        <PageTitle>{t("laws_title")}</PageTitle>
        <p className="mt-2 text-lg text-ink-muted">{t("laws_intro")}</p>
      </div>
      <LawSearchForm />
      {result.status === "error" && <p className="font-semibold text-danger">{t("laws_error")}</p>}
      {result.status === "loading" && <Skeleton className="h-40 rounded-md" />}
      {result.status === "ok" && (
        <ul className="stagger grid gap-x-10 border-t-2 border-ink sm:grid-cols-2">
          {result.data.map((act) => (
            <li key={act.slug}>
              <Link
                to={`/laws/${act.slug}`}
                className="target group flex h-full flex-col gap-1 border-b border-line-subtle px-1 py-3 text-ink motion-colors hover:bg-highlight"
              >
                <span className="flex items-center gap-2 text-lg font-bold">
                  <BookOpen aria-hidden="true" size={18} className="shrink-0 text-brand" />
                  {act.name}
                </span>
                <span className="text-sm text-ink-muted">
                  {t(act.unit === "Article" ? "laws_count_articles" : "laws_count_sections", {
                    year: act.year,
                    count: act.sections,
                  })}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
