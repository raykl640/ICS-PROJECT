import { ArrowUpRight, FileText, MessageSquare, Scale, Sun } from "lucide-react";
import { type CSSProperties, useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router";
import type { UiLanguage } from "../api/types";
import { listConversations, listLetters } from "../api/library";
import { listReads } from "../api/laws";
import { useAuth, useSession } from "../app/contexts";
import { PageTitle } from "../app/PageTitle";
import { Composer } from "../components/Composer";
import { Badge, Card, EmptyState } from "../design/components/Display";
import { isBusy } from "../hooks/session";
import { useLoad } from "../hooks/useLoad";
import { type StringKey, useI18n } from "../i18n";

// The ten Acts with their domain wording (ARCHITECTURE §2; Legal Aid Act from the router's terms, DEVIATIONS D28).
const TOPICS = [
  "constitution",
  "employment",
  "shops",
  "rent",
  "land",
  "consumer",
  "police",
  "cpc",
  "traffic",
  "legal_aid",
] as const;

/** Home: ask a question, see what is covered, pick up the current answer. */
export function Home() {
  const { t } = useI18n();
  const { state, submit } = useSession();
  const { me } = useAuth();
  const signedIn = Boolean(me?.user && !me.locked);
  const navigate = useNavigate();
  const location = useLocation();
  // "Ask about this section" and "Ask instead" arrive with the composer text in the navigation state.
  const prefill = (location.state as { prefill?: string } | null)?.prefill;
  const [question, setQuestion] = useState(prefill ?? "");
  const box = useRef<HTMLTextAreaElement>(null);
  const [seen, setSeen] = useState(location.key);
  if (prefill && seen !== location.key) {
    setSeen(location.key);
    setQuestion(prefill);
  }

  useEffect(() => {
    if (!prefill) return;
    const field = box.current;
    field?.focus();
    field?.setSelectionRange(prefill.length, prefill.length);
  }, [prefill, location.key]);

  const ask = (text: string, language: UiLanguage) => {
    void submit(text, language);
    navigate("/ask");
  };
  const startWith = (act: string) => {
    if (!question.trim()) setQuestion(`${act}: `);
    box.current?.focus();
  };

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-10">
      <div className="flex flex-col gap-10">
        <section className="min-w-0">
          <PageTitle className="text-balance">{t("hero_title")}</PageTitle>
          <p className="mt-2 mb-5 max-w-[60ch] text-ink-muted">{t("hero_body")}</p>
          <Composer
            label={t("question_label")}
            value={question}
            onChange={setQuestion}
            onSubmit={ask}
            busy={isBusy(state.phase)}
            examples
            textareaRef={box}
          />
        </section>

        <section aria-labelledby="topics-title" className="min-w-0">
          <h2 id="topics-title" className="font-display-style border-t-[3px] border-ink pt-3 text-2xl text-ink">
            {t("topics_title")}
          </h2>
          <p className="mt-1 mb-4 text-ink-muted">{t("topics_hint")}</p>
          <ol className="stagger grid gap-x-8 border-t-2 border-ink sm:grid-cols-2">
            {TOPICS.map((topic, index) => {
              const act = t(`act_${topic}` as StringKey);
              return (
                <li key={topic} style={{ "--i": index } as CSSProperties} className="border-b border-line-subtle">
                  <button
                    type="button"
                    onClick={() => startWith(act)}
                    className="group target grid w-full cursor-pointer grid-cols-[2rem_1fr_auto] items-baseline gap-x-2 px-1 py-2.5 text-left motion-colors hover:bg-highlight"
                  >
                    <span aria-hidden="true" className="font-mono text-xs text-ink-muted">
                      {String(index + 1).padStart(2, "0")}
                    </span>
                    <span className="min-w-0">
                      <span className="block font-bold text-ink">{act}</span>
                      <span className="block text-sm text-ink-muted group-hover:text-ink">
                        {t(`domain_${topic}` as StringKey)}
                      </span>
                    </span>
                    <ArrowUpRight
                      aria-hidden="true"
                      size={16}
                      className="self-center text-ink-muted opacity-0 motion-colors group-hover:opacity-100 group-focus-visible:opacity-100"
                    />
                  </button>
                </li>
              );
            })}
          </ol>
        </section>
      </div>

      <div className="grid gap-x-12 gap-y-8 md:grid-cols-2">
        <Card title={t("continue_title")}>
          <SavedRecent />
          <RecentReads />
          {state.phase === "idle" || state.conversationId ? (
            signedIn ? null : (
              <EmptyState icon={<MessageSquare size={24} />} title={t("continue_empty_title")}>
                {t("continue_empty_body")}
              </EmptyState>
            )
          ) : (
            <Link to="/ask" className="-mx-2 flex items-start gap-3 px-2 py-2 text-ink hover:bg-highlight">
              <MessageSquare aria-hidden="true" size={20} className="mt-0.5 shrink-0 text-ink-muted" />
              <span className="min-w-0 flex-1">
                <span className="line-clamp-2 font-semibold">{state.question}</span>
                <span className="mt-1 flex items-center gap-2 text-sm text-ink-muted">
                  <Badge tone={isBusy(state.phase) ? "info" : state.phase === "error" ? "danger" : "success"}>
                    {t(
                      isBusy(state.phase)
                        ? "step_status_current"
                        : state.phase === "error"
                          ? "error_title"
                          : "status_done",
                    )}
                  </Badge>
                  {t("continue_open")}
                </span>
              </span>
            </Link>
          )}
        </Card>
        <Card title={t("today_title")}>
          <EmptyState icon={<Sun size={24} />} title={t("today_empty_title")}>
            {t("today_empty_body")}
          </EmptyState>
        </Card>
      </div>
    </div>
  );
}

const RECENT = "limit=3";

/** Signed in: the latest chats and letters from the library. */
function SavedRecent() {
  const { t } = useI18n();
  const { me } = useAuth();
  const enabled = Boolean(me?.user && !me.locked);
  const chats = useLoad(enabled ? "home-chats" : null, () => listConversations(RECENT)).result;
  const letters = useLoad(enabled ? "home-letters" : null, () => listLetters(RECENT)).result;
  if (!enabled || chats.status !== "ok" || letters.status !== "ok") return null;
  const items = [
    ...chats.data.items.map((c) => ({
      id: c.id,
      href: `/ask/${c.id}`,
      title: c.title,
      icon: MessageSquare,
      busy: c.turns === 0,
    })),
    ...letters.data.items.map((l) => ({
      id: l.id,
      href: `/letters/${l.id}`,
      title: l.title,
      icon: FileText,
      busy: false,
    })),
  ];
  if (items.length === 0) return <p className="text-ink-muted">{t("continue_empty_signed_in")}</p>;
  return (
    <div className="flex flex-col gap-1">
      <ul className="flex flex-col">
        {items.map(({ id, href, title, icon: Icon, busy }) => (
          <li key={id}>
            <Link to={href} className="-mx-2 flex items-start gap-3 px-2 py-2 text-ink hover:bg-highlight">
              <Icon aria-hidden="true" size={20} className="mt-0.5 shrink-0 text-ink-muted" />
              <span className="line-clamp-2 min-w-0 flex-1 font-semibold">{title}</span>
              {busy && <Badge tone="info">{t("answer_in_progress")}</Badge>}
            </Link>
          </li>
        ))}
      </ul>
      <Link
        to="/library"
        className="mt-2 font-semibold text-brand underline underline-offset-3 hover:bg-highlight hover:text-ink"
      >
        {t("library_open")}
      </Link>
    </div>
  );
}

/** Signed in: the sections read most recently ("Continue reading"). */
function RecentReads() {
  const { t } = useI18n();
  const { me } = useAuth();
  const enabled = Boolean(me?.user && !me.locked);
  const reads = useLoad(enabled ? "home-reads" : null, () => listReads(3)).result;
  if (!enabled || reads.status !== "ok" || reads.data.length === 0) return null;
  return (
    <div className="mt-4 border-t border-line-subtle pt-3">
      <h3 className="label-mono mb-1 text-ink-muted">{t("continue_reading")}</h3>
      <ul className="flex flex-col">
        {reads.data.map((read) => (
          <li key={read.chunk_id}>
            <Link
              to={`/laws/act/${read.chunk_id}`}
              className="-mx-2 flex items-start gap-3 px-2 py-2 text-ink hover:bg-highlight"
            >
              <Scale aria-hidden="true" size={20} className="mt-0.5 shrink-0 text-ink-muted" />
              <span className="line-clamp-2 min-w-0 flex-1">
                <span className="font-semibold">{read.act}</span> — {read.section_num}: {read.section_title}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
