import { useEffect } from "react";
import type { SourceChunk } from "../api/types";
import { reduceMotion } from "../app/settings";
import { Badge, Skeleton } from "../design/components/Display";
import { SourceCard } from "../design/components/Legal";
import { useI18n } from "../i18n";
import { sourceId } from "../lib/citations";

export interface Highlight {
  chunkId: string;
  /** Changes on every citation click, so clicking the same citation again scrolls again. */
  nonce: number;
}

/** The retrieved provisions, verbatim, so every claim can be checked; a cited one is scrolled to, focused and marked. */
export function Sources({
  chunks,
  failed,
  highlight,
}: {
  chunks: SourceChunk[] | null;
  failed: boolean;
  highlight: Highlight | null;
}) {
  const { t } = useI18n();

  useEffect(() => {
    if (!highlight) return;
    const element = document.getElementById(sourceId(highlight.chunkId));
    element?.scrollIntoView?.({ behavior: reduceMotion() ? "auto" : "smooth", block: "start" });
    element?.focus({ preventScroll: true });
  }, [highlight, chunks]);

  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-ink-muted">{t("sources_intro")}</p>
      {failed && <p className="font-semibold text-danger">{t("sources_error")}</p>}
      {!chunks && !failed && (
        <div aria-hidden="true" className="flex flex-col gap-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-24 rounded-md" />
          ))}
        </div>
      )}
      {chunks && (
        <ol className="flex flex-col gap-3">
          {chunks.map((chunk) => (
            <li key={chunk.chunk_id}>
              <Source chunk={chunk} highlighted={highlight?.chunkId === chunk.chunk_id} />
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

function Source({ chunk, highlighted }: { chunk: SourceChunk; highlighted: boolean }) {
  const { t } = useI18n();
  const schedule = chunk.unit_type === "schedule";
  const unit = schedule ? "" : t(chunk.unit_type === "article" ? "unit_article" : "unit_section");
  const mark = schedule ? "Sch." : `${chunk.unit_type === "article" ? "Art." : "s."} ${chunk.section_num}`;
  const heading = `${unit ? `${unit} ` : ""}${chunk.section_num} — ${chunk.section_title}`;
  return (
    <SourceCard
      id={sourceId(chunk.chunk_id)}
      act={chunk.act}
      heading={heading}
      mark={mark}
      locator={[chunk.part, t("source_page", { page: chunk.page })].filter(Boolean).join(" · ")}
      regionLabel={`${chunk.act} ${chunk.section_num}`}
      highlighted={highlighted}
      badge={
        chunk.truncated && (
          <p className="text-sm">
            <Badge tone="warn">{t("truncated_badge")}</Badge>{" "}
            <span className="text-ink-muted">{t("truncated_help")}</span>
          </p>
        )
      }
    >
      {chunk.text}
    </SourceCard>
  );
}
