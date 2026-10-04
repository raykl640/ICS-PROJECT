import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { UiLanguage } from "./api/types";
import { BUTTON_SECONDARY } from "./components/buttons";
import { ErrorState, HealthBanner } from "./components/ErrorState";
import { FeedbackBar } from "./components/FeedbackBar";
import { Header } from "./components/Header";
import { NullScreen } from "./components/NullScreen";
import { QueryPanel } from "./components/QueryPanel";
import { ReferralFooter } from "./components/ReferralFooter";
import { ResponsePanel } from "./components/ResponsePanel";
import { type Highlight, SourcesPanel } from "./components/SourcesPanel";
import { isBusy, isEngineError } from "./hooks/session";
import { useHealth } from "./hooks/useHealth";
import { useQuerySession } from "./hooks/useQuerySession";
import { I18nContext, makeTranslate } from "./i18n";
import { isWideScreen } from "./lib/media";
import { withoutDisclaimer } from "./lib/text";

/** HakiAI single page: question, streamed answer in tabs, verbatim sources, feedback. */
export function App() {
  const [language, setLanguage] = useState<UiLanguage>("en");
  const i18n = useMemo(() => ({ language, t: makeTranslate(language) }), [language]);
  const { t } = i18n;
  const { state, submit, retry, reset } = useQuerySession();
  const { health, refresh } = useHealth();
  const [sourcesOpen, setSourcesOpen] = useState(isWideScreen);
  const [highlight, setHighlight] = useState<Highlight | null>(null);
  const questionRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    document.documentElement.lang = language;
    document.title = t("app_title");
  }, [language, t]);

  useEffect(() => {
    if (isEngineError(state.error)) refresh();
  }, [state.error, refresh]);

  const onCite = useCallback((chunkId: string) => {
    setSourcesOpen(true);
    setHighlight((previous) => ({ chunkId, nonce: (previous?.nonce ?? 0) + 1 }));
  }, []);

  const onSubmit = (question: string) => {
    setHighlight(null);
    void submit(question, language);
  };

  const askAgain = () => {
    reset();
    questionRef.current?.focus();
  };

  const idle = state.phase === "idle";
  const answering = state.sessionId !== null && state.phase !== "null" && state.phase !== "error";
  const sections = useMemo(() => withoutDisclaimer(state.translated ?? state.draft), [state.translated, state.draft]);
  const sources = state.sources ?? [];
  const showSources = answering && (state.sources === null || sources.length > 0);
  const finished = state.phase === "done" || state.phase === "null";

  return (
    <I18nContext.Provider value={i18n}>
      <div className="min-h-dvh bg-paper text-ink">
        <Header />
        <main className="mx-auto max-w-6xl space-y-6 px-4 pb-16 sm:px-6 lg:px-8">
          <HealthBanner health={health} />
          {idle && (
            <div className="max-w-3xl pt-4 sm:pt-8">
              <h1 className="font-serif text-4xl leading-tight font-semibold tracking-tight text-balance sm:text-5xl">
                {t("hero_title")}
              </h1>
              <p className="mt-4 text-lg leading-relaxed text-muted sm:text-xl">{t("hero_body")}</p>
            </div>
          )}
          <div className={showSources ? "gap-8 lg:grid lg:grid-cols-[minmax(0,1fr)_minmax(0,25rem)]" : ""}>
            <div className="min-w-0 space-y-6">
              {!idle && <h1 className="sr-only">{t("app_title")}</h1>}
              <QueryPanel
                busy={isBusy(state.phase)}
                compact={!idle}
                onLanguage={setLanguage}
                onSubmit={onSubmit}
                textareaRef={questionRef}
              />
              {idle && (
                <ul className="grid gap-3 sm:grid-cols-3">
                  {(["how_1", "how_2", "how_3"] as const).map((key, index) => (
                    <li key={key} className="flex gap-3 rounded-xl border border-line bg-surface p-4 text-base">
                      <span aria-hidden="true" className="font-serif text-2xl leading-none font-semibold text-brand">
                        {index + 1}
                      </span>
                      <span>{t(key)}</span>
                    </li>
                  ))}
                </ul>
              )}
              {answering && (
                <ResponsePanel
                  key={`answer-${state.sessionId}`}
                  state={state}
                  sections={sections}
                  sources={sources}
                  onCite={onCite}
                />
              )}
              {state.phase === "null" && state.nullInfo && <NullScreen info={state.nullInfo} onAskAgain={askAgain} />}
              {state.phase === "error" && state.error && (
                <ErrorState error={state.error} health={health} onRetry={retry} />
              )}
              {finished && state.sessionId && (
                <FeedbackBar key={`feedback-${state.sessionId}`} sessionId={state.sessionId} />
              )}
              {state.phase === "done" && (
                <>
                  <ReferralFooter />
                  <button type="button" onClick={askAgain} className={BUTTON_SECONDARY}>
                    {t("ask_again")}
                  </button>
                </>
              )}
            </div>
            {showSources && (
              <aside className="mt-6 lg:sticky lg:top-6 lg:mt-0 lg:max-h-[calc(100dvh-3rem)] lg:self-start lg:overflow-y-auto">
                <SourcesPanel
                  chunks={state.sources}
                  failed={state.sourcesFailed}
                  open={sourcesOpen}
                  onToggle={() => setSourcesOpen((open) => !open)}
                  highlight={highlight}
                />
              </aside>
            )}
          </div>
        </main>
        <footer className="border-t border-line">
          <p className="mx-auto max-w-6xl px-4 py-6 text-sm text-muted sm:px-6 lg:px-8">{t("disclaimer")}</p>
        </footer>
      </div>
    </I18nContext.Provider>
  );
}
