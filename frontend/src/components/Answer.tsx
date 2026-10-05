import { ListTree, Square } from "lucide-react";
import { type ReactNode, useState } from "react";
import type { SourceChunk } from "../api/types";
import { Button } from "../design/components/Button";
import { Notice, Skeleton } from "../design/components/Display";
import { AnswerCard } from "../design/components/Legal";
import { cx } from "../design/cx";
import { isBusy, type SessionState } from "../hooks/session";
import { useAnnouncement } from "../hooks/useAnnouncement";
import { type StringKey, type Translate, useI18n } from "../i18n";
import { SECTIONS, type Section, type Sections } from "../lib/sectionSplitter";
import { activeTab } from "../lib/tabs";
import { AnswerMarkdown } from "./AnswerMarkdown";
import { CitationWarning } from "./CitationWarning";
import { LetterTab } from "./LetterTab";
import { Progress } from "./Progress";

const TAB_LABELS: Record<Section, StringKey> = { rights: "tab_rights", steps: "tab_steps", letter: "tab_letter" };

/** Status line text for the current phase. */
function statusText(state: SessionState, t: Translate): string {
  if (state.reconnecting) return t("status_reconnecting");
  switch (state.phase) {
    case "searching":
      return t("status_searching");
    case "retrieved":
      return state.chunkCount === null ? t("status_searching") : t("status_retrieved", { count: state.chunkCount });
    case "queued":
      return t("status_queued", { position: state.queuePosition ?? 1 });
    case "generating":
      return t("status_generating");
    case "translating":
      return t("status_translating");
    default:
      return t("status_done");
  }
}

interface AnswerProps {
  state: SessionState;
  sections: Sections;
  sources: SourceChunk[];
  onCite: (chunkId: string) => void;
  /** Shown when the sources can be opened (null hides the button). */
  onShowSources: (() => void) | null;
  /** Shows a Stop button while the answer is being written. */
  onStop?: () => void;
  /** Replaces the letter tab's download buttons (a saved answer opens the letter workspace instead). */
  letterActions?: ReactNode;
}

/** The streamed answer: progress, tabs that follow the stream until the user picks one, warnings and disclaimer. */
export function Answer({ state, sections, sources, onCite, onShowSources, onStop, letterActions }: AnswerProps) {
  const { t } = useI18n();
  const [chosen, setChosen] = useState<Section | null>(null);
  const busy = isBusy(state.phase);
  const active = activeTab(chosen, state.latest);
  const announcement = useAnnouncement(SECTIONS.map((s) => sections[s]).join("\n"), !busy);
  const draftBanner =
    state.language === "sw" && !state.translated && (state.phase === "generating" || state.phase === "translating");
  const done = state.phase === "done" ? state.done : null;

  return (
    <AnswerCard
      title={t("answer_title")}
      meta={
        <p role="status" className={cx("font-mono text-xs text-ink-muted", busy && !state.reconnecting && "sr-only")}>
          {statusText(state, t)}
        </p>
      }
      status={
        (busy || draftBanner) && (
          <div className="flex flex-col gap-3">
            {busy && <Progress state={state} />}
            {draftBanner && <Notice tone="info" title={t("draft_banner")} />}
            <p className="sr-only" aria-live="polite">
              {announcement}
            </p>
          </div>
        )
      }
      tabs={SECTIONS.map((section) => ({
        id: section,
        label: (
          <>
            {t(TAB_LABELS[section])}
            {busy && state.latest === section && (
              <span className="label-mono bg-highlight px-1.5 py-0.5 font-semibold text-ink">{t("tab_writing")}</span>
            )}
          </>
        ),
        content: (
          <SectionBody
            section={section}
            text={sections[section]}
            state={state}
            sources={sources}
            onCite={onCite}
            streaming={busy && state.latest === section}
            letterActions={letterActions}
          />
        ),
      }))}
      value={active}
      onValueChange={(id) => setChosen(id as Section)}
      busy={busy}
      notes={
        done && (
          <>
            {!done.format_ok && <Notice tone="warn">{t("format_warning")}</Notice>}
            <CitationWarning unmatched={done.citation_check.unmatched} />
            {done.warnings
              .filter((warning) => warning !== t("citation_warning"))
              .map((warning) => (
                <Notice key={warning} tone="info">
                  {warning}
                </Notice>
              ))}
          </>
        )
      }
      actions={
        (onShowSources || (busy && onStop)) && (
          <>
            {onShowSources && (
              <Button icon={<ListTree size={18} />} onClick={onShowSources}>
                {t("sources_open", { count: sources.length })}
              </Button>
            )}
            {busy && onStop && (
              <Button variant="danger" icon={<Square size={16} />} onClick={onStop}>
                {t("stop")}
              </Button>
            )}
          </>
        )
      }
      footer={done?.disclaimer ?? t("disclaimer")}
    />
  );
}

interface BodyProps {
  section: Section;
  text: string;
  state: SessionState;
  sources: SourceChunk[];
  onCite: (chunkId: string) => void;
  streaming: boolean;
  letterActions?: ReactNode;
}

function SectionBody({ section, text, state, sources, onCite, streaming, letterActions }: BodyProps) {
  const { t } = useI18n();
  if (!text) {
    if (!isBusy(state.phase)) return <p className="text-ink-muted">{t("tab_missing")}</p>;
    return (
      <div>
        <p className="text-ink-muted">{t("tab_pending")}</p>
        <div aria-hidden="true" className="mt-4 flex flex-col gap-3">
          {["w-11/12", "w-full", "w-4/5", "w-2/3"].map((width) => (
            <Skeleton key={width} className={width} />
          ))}
        </div>
      </div>
    );
  }
  if (section === "letter") {
    return (
      <LetterTab
        text={text}
        sessionId={state.sessionId ?? ""}
        finished={state.phase === "done"}
        actions={letterActions}
      />
    );
  }
  return (
    <div className={streaming ? "stream-caret" : undefined}>
      <AnswerMarkdown text={text} sources={sources} onCite={onCite} />
    </div>
  );
}
