import { MessageSquare, SearchX } from "lucide-react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { listActs, searchLaws, sectionHref, type SearchHit } from "../api/laws";
import { PageTitle } from "../app/PageTitle";
import { LawSearchForm } from "../components/laws/LawSearchForm";
import { Button } from "../design/components/Button";
import { EmptyState, Skeleton } from "../design/components/Display";
import { useLoad } from "../hooks/useLoad";
import { useI18n } from "../i18n";
import { markSegments } from "../lib/marks";
import { unitName } from "../lib/lawText";

/** Full-text search over the laws: BM25 hits with highlighted snippets and Act filter chips. */
export function Search() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const q = params.get("q")?.trim() ?? "";
  const selected = (params.get("acts") ?? "").split(",").filter(Boolean);
  const acts = useLoad("acts", listActs).result;
  const hits = useLoad(q ? `search-${q}-${selected.join(",")}` : null, () => searchLaws(q, selected)).result;

  const toggle = (slug: string) => {
    const next = selected.includes(slug) ? selected.filter((s) => s !== slug) : [...selected, slug];
    const updated = new URLSearchParams(params);
    if (next.length) updated.set("acts", next.join(","));
    else updated.delete("acts");
    setParams(updated, { replace: true });
  };
  const askInstead = (
    <Button
      variant="primary"
      icon={<MessageSquare size={18} />}
      onClick={() => navigate("/", { state: { prefill: q } })}
    >
      {t("search_ask_instead")}
    </Button>
  );

  return (
    <div className="flex max-w-3xl flex-col gap-5">
      <PageTitle>{t("search_title")}</PageTitle>
      <LawSearchForm key={q} initial={q} acts={selected} />
      {acts.status === "ok" && (
        <div role="group" aria-label={t("search_filter_acts")} className="flex flex-wrap gap-2">
          {acts.data.map((act) => (
            <button
              key={act.slug}
              type="button"
              aria-pressed={selected.includes(act.slug)}
              onClick={() => toggle(act.slug)}
              className="target rounded-full border border-line-subtle bg-raised px-3.5 py-1 text-sm font-semibold text-ink-muted motion-colors hover:text-ink aria-pressed:border-brand aria-pressed:bg-brand aria-pressed:text-brand-ink"
            >
              {act.name}
            </button>
          ))}
        </div>
      )}
      {!q && (
        <EmptyState icon={<SearchX size={28} />} title={t("search_empty_title")}>
          {t("search_empty_body")}
        </EmptyState>
      )}
      {q && hits.status === "loading" && <Skeleton className="h-40 rounded-md" />}
      {q && hits.status === "error" && <p className="font-semibold text-danger">{t("laws_error")}</p>}
      {q && hits.status === "ok" && hits.data.length === 0 && (
        <EmptyState icon={<SearchX size={28} />} title={t("search_none_title")} action={askInstead}>
          {t("search_none_body")}
        </EmptyState>
      )}
      {q && hits.status === "ok" && hits.data.length > 0 && (
        <>
          <p role="status" className="text-ink-muted">
            {t("search_count", { count: hits.data.length })}
          </p>
          <ol className="flex flex-col gap-3">
            {hits.data.map((hit) => (
              <li key={hit.chunk_id}>
                <Hit hit={hit} />
              </li>
            ))}
          </ol>
          <div>{askInstead}</div>
        </>
      )}
    </div>
  );
}

function Hit({ hit }: { hit: SearchHit }) {
  const { t } = useI18n();
  return (
    <article className="border-t border-line-subtle pt-5">
      <h2 className="font-semibold text-ink">
        <Link to={sectionHref(hit.chunk_id, hit.act_slug)} className="text-brand underline-offset-3 hover:underline">
          {hit.act}, {unitName(t, hit.unit_type, hit.num)}: {hit.title}
        </Link>
      </h2>
      <p className="mt-2 font-reading text-ink">
        {markSegments(hit.snippet, hit.marks).map((segment, n) =>
          segment.mark ? (
            <mark key={n} className="rounded-sm bg-accent/25 px-0.5 text-ink">
              {segment.text}
            </mark>
          ) : (
            <span key={n}>{segment.text}</span>
          ),
        )}
      </p>
    </article>
  );
}
