import { ChevronLeft } from "lucide-react";
import { Link, useParams } from "react-router";
import { getAct, sectionHref } from "../api/laws";
import { PageTitle } from "../app/PageTitle";
import { LawSearchForm } from "../components/laws/LawSearchForm";
import { Badge, Skeleton } from "../design/components/Display";
import { useLoad } from "../hooks/useLoad";
import { useI18n } from "../i18n";
import { unitName } from "../lib/lawText";
import { NotFound } from "./NotFound";

/** An Act's table of contents grouped by Chapter/Part; repealed units are greyed. */
export function LawAct() {
  const { t } = useI18n();
  const { act = "" } = useParams();
  const { result } = useLoad(`act-${act}`, () => getAct(act));
  if (result.status === "error")
    return result.notFound ? <NotFound /> : <p className="text-danger">{t("laws_error")}</p>;
  if (result.status === "loading") return <Skeleton className="h-64 rounded-md" />;
  const { act: info, groups } = result.data;
  return (
    <div className="flex max-w-3xl flex-col gap-6">
      <div>
        <Link
          to="/laws"
          className="inline-flex items-center gap-1 font-semibold text-brand underline underline-offset-3"
        >
          <ChevronLeft aria-hidden="true" size={18} />
          {t("laws_title")}
        </Link>
        <PageTitle className="mt-2">{info.name}</PageTitle>
        <p className="mt-1 text-ink-muted">
          {t(info.unit === "Article" ? "laws_count_articles" : "laws_count_sections", {
            year: info.year,
            count: info.sections,
          })}
        </p>
      </div>
      <LawSearchForm acts={[info.slug]} />
      <nav aria-label={t("laws_toc")} className="flex flex-col gap-5">
        {groups.map((group, n) => (
          <section key={`${group.part}-${n}`} aria-label={group.part || info.name}>
            {group.part && <h2 className="mb-2 font-display-style text-lg text-ink">{group.part}</h2>}
            <ol className="flex flex-col">
              {group.items.map((item) => (
                <li key={item.chunk_id}>
                  <Link
                    to={sectionHref(item.chunk_id, info.slug)}
                    className={`-mx-2 flex items-baseline gap-3 rounded-md px-2 py-1.5 hover:bg-sunken ${item.repealed ? "text-ink-muted" : "text-ink"}`}
                  >
                    <span className="w-28 shrink-0 font-semibold">{unitName(t, item.unit_type, item.num)}</span>
                    <span className="min-w-0 flex-1">{item.title}</span>
                    {item.repealed && <Badge>{t("laws_repealed")}</Badge>}
                  </Link>
                </li>
              ))}
            </ol>
          </section>
        ))}
      </nav>
    </div>
  );
}
