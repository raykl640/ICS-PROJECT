import { type KeyboardEvent, useRef, useState } from "react";
import type { SourceChunk } from "../api/types";
import { isBusy, type SessionState } from "../hooks/session";
import { useAnnouncement } from "../hooks/useAnnouncement";
import { type StringKey, useI18n } from "../i18n";
import { SECTIONS, type Section, type Sections } from "../lib/sectionSplitter";
import { activeTab } from "../lib/tabs";
import { AnswerMarkdown } from "./AnswerMarkdown";
import { Banner } from "./Banner";
import { CitationWarning } from "./CitationWarning";
import { LetterTab } from "./LetterTab";

const TAB_LABELS: Record<Section, StringKey> = { rights: "tab_rights", steps: "tab_steps", letter: "tab_letter" };

interface Props {
  state: SessionState;
  sections: Sections;
  sources: SourceChunk[];
  onCite: (chunkId: string) => void;
}

/** Status line text for the current phase. */
function statusText(state: SessionState, t: ReturnType<typeof useI18n>["t"]): string {
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

/** The streamed answer in three tabs that follow the stream until the user picks one; status, banners, disclaimer. */
export function ResponsePanel({ state, sections, sources, onCite }: Props) {
  const { t } = useI18n();
  const [chosen, setChosen] = useState<Section | null>(null);
  const tabs = useRef<Partial<Record<Section, HTMLButtonElement | null>>>({});
  const busy = isBusy(state.phase);
  const active = activeTab(chosen, state.latest);
  const announcement = useAnnouncement(SECTIONS.map((s) => sections[s]).join("\n"), !busy);
  const draftBanner =
    state.language === "sw" && !state.translated && (state.phase === "generating" || state.phase === "translating");

  const onKeyDown = (event: KeyboardEvent) => {
    const index = SECTIONS.indexOf(active);
    const next = { ArrowRight: index + 1, ArrowLeft: index - 1, Home: 0, End: SECTIONS.length - 1 }[event.key];
    if (next === undefined) return;
    event.preventDefault();
    const section = SECTIONS[(next + SECTIONS.length) % SECTIONS.length];
    setChosen(section);
    tabs.current[section]?.focus();
  };

  return (
    <section aria-labelledby="answer-title" className="rounded-2xl border border-line bg-surface">
      <div className="flex flex-wrap items-baseline justify-between gap-2 px-4 pt-4 sm:px-6 sm:pt-5">
        <h2 id="answer-title" className="font-serif text-2xl font-semibold">
          {t("answer_title")}
        </h2>
        <p role="status" className="flex items-center gap-2 text-base text-muted">
          {busy && <span aria-hidden="true" className="size-2.5 animate-pulse rounded-full bg-brand" />}
          {statusText(state, t)}
        </p>
      </div>
      <p className="sr-only" aria-live="polite">
        {announcement}
      </p>

      {draftBanner && (
        <div className="px-4 pt-4 sm:px-6">
          <Banner tone="info" title={t("draft_banner")} />
        </div>
      )}

      <div
        role="tablist"
        aria-label={t("answer_title")}
        onKeyDown={onKeyDown}
        className="mt-4 grid grid-cols-3 border-b border-line px-1 sm:flex sm:gap-1 sm:px-4"
      >
        {SECTIONS.map((section) => {
          const selected = section === active;
          const writing = busy && state.latest === section;
          return (
            <button
              key={section}
              ref={(element) => {
                tabs.current[section] = element;
              }}
              type="button"
              role="tab"
              id={`tab-${section}`}
              aria-selected={selected}
              aria-controls={`panel-${section}`}
              tabIndex={selected ? 0 : -1}
              onClick={() => setChosen(section)}
              className={`relative -mb-px flex min-h-11 flex-col items-center justify-center gap-1 border-b-[3px] px-1.5 py-2 text-center text-sm leading-tight font-semibold sm:flex-row sm:gap-2 sm:px-4 sm:text-base sm:whitespace-nowrap ${
                selected ? "border-brand text-ink" : "border-transparent text-muted hover:text-ink"
              }`}
            >
              {t(TAB_LABELS[section])}
              {writing && (
                <span className="rounded-full bg-brand-soft px-2 py-0.5 text-xs leading-none font-semibold text-brand-strong">
                  {t("tab_writing")}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {SECTIONS.map((section) => (
        <div
          key={section}
          role="tabpanel"
          id={`panel-${section}`}
          aria-labelledby={`tab-${section}`}
          aria-busy={busy}
          hidden={section !== active}
          tabIndex={0}
          className="px-4 py-5 text-[1.0625rem] leading-relaxed sm:px-6 sm:text-lg"
        >
          <SectionBody
            section={section}
            text={sections[section]}
            state={state}
            sources={sources}
            onCite={onCite}
            streaming={busy && state.latest === section}
          />
        </div>
      ))}

      {state.phase === "done" && state.done && (
        <div className="space-y-3 border-t border-line px-4 py-4 sm:px-6">
          {!state.done.format_ok && <Banner tone="warn">{t("format_warning")}</Banner>}
          <CitationWarning unmatched={state.done.citation_check.unmatched} />
          {state.done.warnings
            .filter((warning) => warning !== t("citation_warning"))
            .map((warning) => (
              <Banner key={warning} tone="info">
                {warning}
              </Banner>
            ))}
          <p className="text-sm text-muted">{state.done.disclaimer}</p>
        </div>
      )}
    </section>
  );
}

interface BodyProps {
  section: Section;
  text: string;
  state: SessionState;
  sources: SourceChunk[];
  onCite: (chunkId: string) => void;
  streaming: boolean;
}

function SectionBody({ section, text, state, sources, onCite, streaming }: BodyProps) {
  const { t } = useI18n();
  if (!text) {
    if (!isBusy(state.phase)) return <p className="text-muted">{t("tab_missing")}</p>;
    return (
      <div>
        <p className="text-base text-muted">{t("tab_pending")}</p>
        <div aria-hidden="true" className="mt-4 space-y-3">
          {["w-11/12", "w-full", "w-4/5", "w-2/3"].map((width) => (
            <div key={width} className={`h-4 animate-pulse rounded bg-sunken ${width}`} />
          ))}
        </div>
      </div>
    );
  }
  if (section === "letter") {
    return <LetterTab text={text} sessionId={state.sessionId ?? ""} finished={state.phase === "done"} />;
  }
  return (
    <div className={streaming ? "stream-caret" : undefined}>
      <AnswerMarkdown text={text} sources={sources} onCite={onCite} />
    </div>
  );
}
