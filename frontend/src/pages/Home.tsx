import { ArrowRight, FileText, MessageSquare } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router";
import type { UiLanguage } from "../api/types";
import { listConversations, listLetters } from "../api/library";
import { useAuth, useSession } from "../app/contexts";
import { PageTitle } from "../app/PageTitle";
import { Composer } from "../components/Composer";
import { Badge } from "../design/components/Display";
import { isBusy } from "../hooks/session";
import { useLoad } from "../hooks/useLoad";
import { useI18n } from "../i18n";

/** Where a question starts: one box, a few examples, and (signed in) the latest saved work. Answers live at /ask. */
export function Home() {
  const { t } = useI18n();
  const { state, submit } = useSession();
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
  // An unsaved answer from this visit: one link back to it.
  const current = state.phase !== "idle" && !state.conversationId;

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-12 pt-2 lg:pt-10">
      <section className="flex flex-col gap-6">
        <div>
          <PageTitle className="text-balance">{t("hero_title")}</PageTitle>
          <p className="mt-3 text-lg text-ink-muted">{t("hero_body")}</p>
        </div>
        {current && (
          <Link
            to="/ask"
            className="flex items-center gap-3 rounded-md bg-sunken px-4 py-3 text-ink motion-colors hover:bg-line-subtle"
          >
            <MessageSquare aria-hidden="true" size={18} className="shrink-0 text-ink-muted" />
            <span className="min-w-0 flex-1">
              <span className="block text-sm text-ink-muted">{t("current_question")}</span>
              <span className="line-clamp-1 font-semibold">{state.question}</span>
            </span>
            {isBusy(state.phase) && <Badge tone="info">{t("answer_in_progress")}</Badge>}
            <ArrowRight aria-hidden="true" size={18} className="shrink-0 text-ink-muted" />
          </Link>
        )}
        <Composer
          label={t("question_label")}
          value={question}
          onChange={setQuestion}
          onSubmit={ask}
          busy={isBusy(state.phase)}
          examples
          textareaRef={box}
        />
        <p className="text-sm text-ink-muted">
          {t("home_scope")}{" "}
          <Link to="/laws" className="font-semibold text-brand underline-offset-3 hover:underline">
            {t("home_browse")}
          </Link>
        </p>
      </section>
      <SavedRecent />
    </div>
  );
}

const RECENT = "limit=3";

/** Signed in: the latest chats and letters from the library (nothing at all for guests or an empty library). */
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
  if (items.length === 0) return null;
  return (
    <section aria-labelledby="recent-title">
      <div className="mb-2 flex items-baseline justify-between gap-3">
        <h2 id="recent-title" className="text-sm font-semibold text-ink-muted">
          {t("recent_title")}
        </h2>
        <Link to="/library" className="text-sm font-semibold text-brand underline-offset-3 hover:underline">
          {t("library_open")}
        </Link>
      </div>
      <ul className="flex flex-col divide-y divide-line-subtle">
        {items.map(({ id, href, title, icon: Icon, busy }) => (
          <li key={id}>
            <Link
              to={href}
              className="-mx-3 flex items-center gap-3 rounded-md px-3 py-2.5 text-ink motion-colors hover:bg-sunken"
            >
              <Icon aria-hidden="true" size={18} className="shrink-0 text-ink-muted" />
              <span className="line-clamp-1 min-w-0 flex-1">{title}</span>
              {busy && <Badge tone="info">{t("answer_in_progress")}</Badge>}
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
