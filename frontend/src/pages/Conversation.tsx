import { FilePen, MessageSquareX } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, Navigate, useNavigate, useParams } from "react-router";
import { addBookmark, createLetter, getConversation, listBookmarks, type Turn } from "../api/library";
import type { SourceChunk, UiLanguage } from "../api/types";
import { useAuth, useLibrary, useSession } from "../app/contexts";
import { PageTitle } from "../app/PageTitle";
import { Answer } from "../components/Answer";
import { Composer } from "../components/Composer";
import { ErrorState } from "../components/ErrorState";
import { FeedbackBar } from "../components/FeedbackBar";
import { NullScreen } from "../components/NullScreen";
import { ReferralFooter } from "../components/ReferralFooter";
import { type Highlight, Sources } from "../components/Sources";
import { Button } from "../design/components/Button";
import { EmptyState, Notice } from "../design/components/Display";
import { SplitView } from "../design/components/Shell";
import { useToast } from "../design/components/toastContext";
import { isBusy, type SessionState } from "../hooks/session";
import { useLoad } from "../hooks/useLoad";
import { useI18n } from "../i18n";
import { withoutDisclaimer } from "../lib/text";
import { turnState } from "../lib/turnState";

const wideScreen = () => typeof window.matchMedia === "function" && window.matchMedia("(min-width: 1280px)").matches;
const LIVE = "live";

/** Which answer's sources the side panel shows, and the cited provision to highlight. */
interface Focus {
  turn: string;
  highlight: Highlight | null;
}

/** Ask: a new question (/ask), or a saved conversation with follow-ups (/ask/:conversationId). */
export function Conversation() {
  const { conversationId } = useParams();
  return conversationId ? <Thread key={conversationId} id={conversationId} /> : <NewQuestion />;
}

/** Sources panel state shared by both views. */
function useSourcesPanel(initial: string) {
  const [open, setOpen] = useState(wideScreen);
  const [focus, setFocus] = useState<Focus>({ turn: initial, highlight: null });
  const cite = useCallback((turn: string, chunkId: string) => {
    setOpen(true);
    setFocus((previous) => ({ turn, highlight: { chunkId, nonce: (previous.highlight?.nonce ?? 0) + 1 } }));
  }, []);
  const show = useCallback((turn: string) => {
    setFocus((previous) => (previous.turn === turn ? previous : { turn, highlight: null }));
    setOpen((current) => !current || !wideScreen());
  }, []);
  return { open, setOpen, focus, setFocus, cite, show };
}

/** Signed in: saved sections and a way to save one (bookmarks). */
function useBookmarks(enabled: boolean) {
  const { t } = useI18n();
  const toast = useToast();
  const { bump } = useLibrary();
  const { result } = useLoad(enabled ? "bookmarks-saved" : null, () => listBookmarks());
  return useMemo(() => {
    if (!enabled) return undefined;
    const saved = new Set(result.status === "ok" ? result.data.items.map((b) => b.chunk_id) : []);
    const save = (chunkId: string) =>
      void addBookmark(chunkId).then(
        () => {
          bump();
          toast({ title: t("bookmarked"), tone: "success" });
        },
        () => toast({ title: t("library_error"), tone: "danger" }),
      );
    return { saved, save };
  }, [enabled, result, bump, t, toast]);
}

function QuestionBubble({ text }: { text: string }) {
  const { t } = useI18n();
  return (
    <p className="font-display-style text-2xl leading-snug whitespace-pre-wrap text-ink sm:text-[1.75rem]">
      <span className="sr-only">{t("you_asked")} </span>
      {text}
    </p>
  );
}

/** The live (in-memory) answer: progress, Stop, background notice, null, error, feedback. */
function LiveAnswer({
  state,
  onCite,
  onShowSources,
}: {
  state: SessionState;
  onCite: (chunkId: string) => void;
  onShowSources: (() => void) | null;
}) {
  const { t } = useI18n();
  const { retry, stopAnswer, health } = useSession();
  const sections = useMemo(() => withoutDisclaimer(state.translated ?? state.draft), [state.translated, state.draft]);
  const busy = isBusy(state.phase);
  const answering = state.sessionId !== null && state.phase !== "null" && state.phase !== "error";
  const finished = state.phase === "done" || state.phase === "null";
  return (
    <>
      <QuestionBubble text={state.question} />
      {busy && state.background && <Notice tone="info">{t("background_note")}</Notice>}
      {answering && (
        <Answer
          key={`answer-${state.sessionId}`}
          state={state}
          sections={sections}
          sources={state.sources ?? []}
          onCite={onCite}
          onShowSources={onShowSources}
          onStop={stopAnswer}
        />
      )}
      {state.phase === "null" && state.nullInfo && <NullScreen info={state.nullInfo} />}
      {state.phase === "error" && state.error && <ErrorState error={state.error} health={health} onRetry={retry} />}
      {finished && state.sessionId && <FeedbackBar key={`feedback-${state.sessionId}`} sessionId={state.sessionId} />}
      {state.phase === "done" && <ReferralFooter />}
    </>
  );
}

/** /ask: one question at a time (guests, private mode); a saved question moves to its conversation. */
function NewQuestion() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const { state, submit } = useSession();
  const { me } = useAuth();
  const [question, setQuestion] = useState("");
  const box = useRef<HTMLTextAreaElement>(null);
  const panel = useSourcesPanel(LIVE);
  const bookmarks = useBookmarks(Boolean(me?.user && !me.locked));
  // A question saved in a conversation is shown there; this page then offers a fresh question.
  const saved = state.conversationId !== null;

  useEffect(() => {
    if (saved && isBusy(state.phase)) navigate(`/ask/${state.conversationId}`, { replace: true });
  }, [saved, state.phase, state.conversationId, navigate]);

  const ask = (text: string, language: UiLanguage) => {
    panel.setFocus({ turn: LIVE, highlight: null });
    setQuestion("");
    void submit(text, language);
  };
  const idle = state.phase === "idle" || saved;
  const busy = isBusy(state.phase);
  const composer = (
    <Composer
      label={idle ? t("question_label") : t("ask_again")}
      value={question}
      onChange={setQuestion}
      onSubmit={ask}
      busy={busy && !saved}
      examples={idle}
      compact={!idle}
      textareaRef={box}
    />
  );

  // Nothing asked yet: questions start on Home.
  if (idle) return <Navigate to="/" replace />;

  const sources = state.sources ?? [];
  const answering = state.sessionId !== null && state.phase !== "null" && state.phase !== "error";
  const showSources = answering && (state.sources === null || sources.length > 0);
  return (
    <SplitView
      main={
        <div className="flex max-w-3xl flex-col gap-6">
          <PageTitle hidden>{t("answer_page_title")}</PageTitle>
          <LiveAnswer
            state={state}
            onCite={(chunkId) => panel.cite(LIVE, chunkId)}
            onShowSources={showSources ? () => panel.show(LIVE) : null}
          />
          {!busy && (
            <section className="sticky bottom-[4.25rem] z-10 bg-canvas pt-2 pb-3 lg:bottom-0">{composer}</section>
          )}
        </div>
      }
      aside={
        <Sources
          chunks={state.sources}
          failed={state.sourcesFailed}
          highlight={panel.focus.highlight}
          bookmarks={bookmarks}
        />
      }
      asideTitle={t("sources_title")}
      asideOpen={showSources && panel.open}
      onAsideOpenChange={panel.setOpen}
      closeLabel={t("sources_close")}
    />
  );
}

/** /ask/:id: the saved thread, the answer being written (followed even after a reload), and a follow-up box. */
function Thread({ id }: { id: string }) {
  const { t } = useI18n();
  const { state, submit, attach } = useSession();
  const { result, reload } = useLoad(`conversation:${id}`, () => getConversation(id));
  const [question, setQuestion] = useState("");
  const box = useRef<HTMLTextAreaElement>(null);
  const panel = useSourcesPanel(LIVE);
  const bookmarks = useBookmarks(true);
  const attached = useRef<string | null>(null);

  const data = result.status === "ok" ? result.data : null;
  const savedSessions = useMemo(() => new Set(data?.thread.map((turn) => turn.session_id)), [data]);
  const mine = state.conversationId === id || state.followUpOf === id;
  const live = mine && state.phase !== "idle" && !(state.sessionId && savedSessions.has(state.sessionId));
  const busy = live && isBusy(state.phase);

  // After a reload (or from another page) follow an answer the server is still writing for this conversation.
  const running = data?.running[0];
  useEffect(() => {
    if (!running || attached.current === running.session_id) return;
    if (state.sessionId === running.session_id) return;
    if (mine && isBusy(state.phase)) return;
    attached.current = running.session_id;
    attach(running.session_id, running.question, id);
  }, [running, state.sessionId, state.phase, mine, attach, id]);

  // The live answer ended: its turn may now be saved.
  const ended = live && !isBusy(state.phase);
  useEffect(() => {
    if (ended) reload();
  }, [ended, reload]);

  if (result.status === "loading") return <p role="status">{t("loading")}</p>;
  if (result.status === "error" || !data) {
    return (
      <EmptyState
        icon={<MessageSquareX size={32} />}
        title={t(result.status === "error" && result.notFound ? "conversation_not_found" : "library_error")}
      >
        <Link to="/library" className="font-semibold text-brand underline underline-offset-3">
          {t("library_open")}
        </Link>
      </EmptyState>
    );
  }

  const thread = data.thread;
  const focused: SourceChunk[] | null =
    panel.focus.turn === LIVE && live
      ? state.sources
      : ((thread.find((turn) => turn.id === panel.focus.turn) ?? thread[thread.length - 1])?.sources ?? null);
  const hasSources = (focused?.length ?? 0) > 0 || (panel.focus.turn === LIVE && live && state.sources === null);
  const ask = (text: string, language: UiLanguage) => {
    panel.setFocus({ turn: LIVE, highlight: null });
    setQuestion("");
    void submit(text, language, id);
  };

  return (
    <SplitView
      main={
        <div className="flex max-w-3xl flex-col gap-10">
          <PageTitle hidden>{data.title}</PageTitle>
          {thread.map((turn) => (
            <SavedTurn
              key={turn.id}
              turn={turn}
              onCite={(chunkId) => panel.cite(turn.id, chunkId)}
              onShowSources={turn.sources.length ? () => panel.show(turn.id) : null}
            />
          ))}
          {live && (
            <LiveAnswer
              state={state}
              onCite={(chunkId) => panel.cite(LIVE, chunkId)}
              onShowSources={() => panel.show(LIVE)}
            />
          )}
          {!busy && (
            <section className="sticky bottom-[4.25rem] z-10 bg-canvas pt-2 pb-3 lg:bottom-0">
              <p className="mb-2 text-sm text-ink-muted">{t("followup_hint")}</p>
              <Composer
                label={t("followup_label")}
                value={question}
                onChange={setQuestion}
                onSubmit={ask}
                busy={busy}
                compact
                textareaRef={box}
              />
            </section>
          )}
        </div>
      }
      aside={<Sources chunks={focused} failed={false} highlight={panel.focus.highlight} bookmarks={bookmarks} />}
      asideTitle={t("sources_title")}
      asideOpen={hasSources && panel.open}
      onAsideOpenChange={panel.setOpen}
      closeLabel={t("sources_close")}
    />
  );
}

/** A saved question and its answer (or the fallback), with "Edit this letter" instead of downloads. */
function SavedTurn({
  turn,
  onCite,
  onShowSources,
}: {
  turn: Turn;
  onCite: (chunkId: string) => void;
  onShowSources: (() => void) | null;
}) {
  const { t } = useI18n();
  const state = useMemo(() => turnState(turn, t("disclaimer")), [turn, t]);
  const sections = useMemo(() => withoutDisclaimer(turn.sections), [turn.sections]);
  return (
    <article className="flex flex-col gap-6" aria-label={turn.question}>
      <QuestionBubble text={turn.question} />
      {turn.null_response ? (
        <NullScreen info={{ message: t("fallback"), disclaimer: t("disclaimer") }} />
      ) : (
        <Answer
          state={state}
          sections={sections}
          sources={turn.sources}
          onCite={onCite}
          onShowSources={onShowSources}
          letterActions={<OpenLetter turn={turn} />}
        />
      )}
    </article>
  );
}

function OpenLetter({ turn }: { turn: Turn }) {
  const { t } = useI18n();
  const navigate = useNavigate();
  const { bump } = useLibrary();
  const [busy, setBusy] = useState(false);
  const open = async () => {
    setBusy(true);
    try {
      const letter = await createLetter({ turn_id: turn.id, title: turn.question.slice(0, 60) });
      bump();
      navigate(`/letters/${letter.id}`);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Button variant="primary" icon={<FilePen size={18} />} onClick={() => void open()} disabled={busy}>
      {t("open_letter_workspace")}
    </Button>
  );
}
