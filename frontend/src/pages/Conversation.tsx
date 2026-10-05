import { useCallback, useMemo, useRef, useState } from "react";
import type { UiLanguage } from "../api/types";
import { useSession } from "../app/contexts";
import { PageTitle } from "../app/PageTitle";
import { Answer } from "../components/Answer";
import { Composer } from "../components/Composer";
import { ErrorState } from "../components/ErrorState";
import { FeedbackBar } from "../components/FeedbackBar";
import { NullScreen } from "../components/NullScreen";
import { ReferralFooter } from "../components/ReferralFooter";
import { type Highlight, Sources } from "../components/Sources";
import { SplitView } from "../design/components/Shell";
import { isBusy } from "../hooks/session";
import { useI18n } from "../i18n";
import { withoutDisclaimer } from "../lib/text";

const wideScreen = () => typeof window.matchMedia === "function" && window.matchMedia("(min-width: 1024px)").matches;

/** Ask: the question, its streamed answer with sources beside it (a sheet on small screens), feedback and a new question. */
export function Conversation() {
  const { t } = useI18n();
  const { state, submit, retry, health } = useSession();
  const [question, setQuestion] = useState("");
  const [sourcesOpen, setSourcesOpen] = useState(wideScreen);
  const [highlight, setHighlight] = useState<Highlight | null>(null);
  const box = useRef<HTMLTextAreaElement>(null);

  const onCite = useCallback((chunkId: string) => {
    setSourcesOpen(true);
    setHighlight((previous) => ({ chunkId, nonce: (previous?.nonce ?? 0) + 1 }));
  }, []);
  const ask = (text: string, language: UiLanguage) => {
    setHighlight(null);
    setQuestion("");
    void submit(text, language);
  };

  const sections = useMemo(() => withoutDisclaimer(state.translated ?? state.draft), [state.translated, state.draft]);
  const idle = state.phase === "idle";
  const busy = isBusy(state.phase);
  const answering = state.sessionId !== null && state.phase !== "null" && state.phase !== "error";
  const sources = state.sources ?? [];
  const showSources = answering && (state.sources === null || sources.length > 0);
  const finished = state.phase === "done" || state.phase === "null";

  const composer = (
    <Composer
      label={idle ? t("question_label") : t("ask_again")}
      value={question}
      onChange={setQuestion}
      onSubmit={ask}
      busy={busy}
      examples={idle}
      compact={!idle}
      textareaRef={box}
    />
  );

  if (idle) {
    return (
      <section className="max-w-3xl rounded-lg border border-line-subtle bg-surface p-4 shadow-raised sm:p-6">
        <PageTitle className="mb-5">{t("ask_title")}</PageTitle>
        {composer}
      </section>
    );
  }

  const main = (
    <div className="flex flex-col gap-5">
      <PageTitle hidden>{t("answer_page_title")}</PageTitle>
      <p className="ml-auto max-w-[36rem] rounded-lg rounded-br-sm bg-sunken px-4 py-3 text-ink">
        <span className="sr-only">{t("you_asked")} </span>
        {state.question}
      </p>
      {answering && (
        <Answer
          key={`answer-${state.sessionId}`}
          state={state}
          sections={sections}
          sources={sources}
          onCite={onCite}
          onShowSources={showSources ? () => setSourcesOpen((open) => !open || !wideScreen()) : null}
        />
      )}
      {state.phase === "null" && state.nullInfo && (
        <NullScreen info={state.nullInfo} onAskAgain={() => box.current?.focus()} />
      )}
      {state.phase === "error" && state.error && <ErrorState error={state.error} health={health} onRetry={retry} />}
      {finished && state.sessionId && <FeedbackBar key={`feedback-${state.sessionId}`} sessionId={state.sessionId} />}
      {state.phase === "done" && <ReferralFooter />}
      {!busy && <section className="rounded-lg border border-line-subtle bg-surface p-4 sm:p-5">{composer}</section>}
    </div>
  );

  return (
    <SplitView
      main={main}
      aside={<Sources chunks={state.sources} failed={state.sourcesFailed} highlight={highlight} />}
      asideTitle={t("sources_title")}
      asideOpen={showSources && sourcesOpen}
      onAsideOpenChange={setSourcesOpen}
      closeLabel={t("sources_close")}
    />
  );
}
