import { useEffect } from "react";
import type { SourceChunk } from "../api/types";
import { useI18n } from "../i18n";
import { prefersReducedMotion } from "../lib/media";

export interface Highlight {
  chunkId: string;
  nonce: number;
}

interface Props {
  chunks: SourceChunk[] | null;
  failed: boolean;
  open: boolean;
  onToggle: () => void;
  highlight: Highlight | null;
}

/** The retrieved provisions, verbatim, so every claim can be checked; a cited chunk is scrolled to and highlighted. */
export function SourcesPanel({ chunks, failed, open, onToggle, highlight }: Props) {
  const { t } = useI18n();

  useEffect(() => {
    if (!open || !highlight) return;
    const element = document.getElementById(`source-${highlight.chunkId}`);
    element?.scrollIntoView?.({ behavior: prefersReducedMotion() ? "auto" : "smooth", block: "start" });
    element?.focus({ preventScroll: true });
  }, [open, highlight]);

  return (
    <section aria-labelledby="sources-title" className="rounded-2xl border border-line bg-surface p-4 sm:p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="sources-title" className="font-serif text-xl font-semibold">
          {t("sources_title")}
          {chunks && chunks.length > 0 && (
            <span className="ml-2 text-base font-normal text-muted">({chunks.length})</span>
          )}
        </h2>
        <button
          type="button"
          aria-expanded={open}
          aria-controls="sources-list"
          onClick={onToggle}
          className="inline-flex min-h-11 items-center gap-2 rounded-lg px-3 font-semibold text-brand-strong hover:bg-brand-soft"
        >
          <span aria-hidden="true" className={`inline-block transition-transform ${open ? "rotate-90" : ""}`}>
            ›
          </span>
          {open ? t("sources_hide") : t("sources_toggle")}
        </button>
      </div>
      <div id="sources-list" hidden={!open}>
        <p className="mt-2 text-sm text-muted">{t("sources_intro")}</p>
        {failed && <p className="mt-3 text-danger-ink">{t("sources_error")}</p>}
        {!chunks && !failed && <SourceSkeleton />}
        {chunks && (
          <ol className="mt-4 space-y-4">
            {chunks.map((chunk) => (
              <SourceCard key={chunk.chunk_id} chunk={chunk} highlighted={highlight?.chunkId === chunk.chunk_id} />
            ))}
          </ol>
        )}
      </div>
    </section>
  );
}

function SourceCard({ chunk, highlighted }: { chunk: SourceChunk; highlighted: boolean }) {
  const { t } = useI18n();
  const isSchedule = chunk.unit_type === "schedule";
  const unit = isSchedule ? "" : t(chunk.unit_type === "article" ? "unit_article" : "unit_section");
  const margin = isSchedule ? "Sch." : `${chunk.unit_type === "article" ? "Art." : "s."} ${chunk.section_num}`;
  return (
    <li
      id={`source-${chunk.chunk_id}`}
      tabIndex={-1}
      data-highlighted={highlighted}
      className="source-card scroll-mt-4 rounded-xl border border-line bg-paper transition-shadow"
    >
      <article aria-label={`${chunk.act}, ${unit} ${chunk.section_num}`.replace(/ {2,}/g, " ")}>
        <header className="flex gap-3 border-b border-line px-4 py-3">
          <span
            aria-hidden="true"
            className="w-14 shrink-0 pt-0.5 font-serif text-lg leading-tight font-semibold text-brand"
          >
            {margin}
          </span>
          <div className="min-w-0">
            <p className="text-sm font-semibold tracking-wide text-muted uppercase">{chunk.act}</p>
            <h3 className="font-serif text-lg leading-snug font-semibold">
              {unit && `${unit} ${chunk.section_num} — `}
              {isSchedule && `${chunk.section_num} — `}
              {chunk.section_title}
            </h3>
            <p className="mt-0.5 text-sm text-muted">
              {chunk.part && `${chunk.part} · `}
              {t("source_page", { page: chunk.page })}
            </p>
            {chunk.truncated && (
              <p className="mt-2 text-sm">
                <span className="rounded-full border border-warn-line bg-warn-bg px-2 py-0.5 font-semibold text-warn-ink">
                  {t("truncated_badge")}
                </span>{" "}
                <span className="text-muted">{t("truncated_help")}</span>
              </p>
            )}
          </div>
        </header>
        <div
          tabIndex={0}
          role="region"
          aria-label={`${chunk.act} ${chunk.section_num}`}
          className="source-text max-h-96 overflow-y-auto px-4 py-3 font-serif text-base leading-relaxed whitespace-pre-wrap"
        >
          {chunk.text}
        </div>
      </article>
    </li>
  );
}

function SourceSkeleton() {
  return (
    <div aria-hidden="true" className="mt-4 space-y-3">
      {[0, 1, 2].map((i) => (
        <div key={i} className="h-24 animate-pulse rounded-xl bg-sunken" />
      ))}
    </div>
  );
}
