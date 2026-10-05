import { BookOpen, MessageSquare, Sun } from "lucide-react";
import { useRef, useState } from "react";
import { Link, useNavigate } from "react-router";
import type { UiLanguage } from "../api/types";
import { useSession } from "../app/contexts";
import { PageTitle } from "../app/PageTitle";
import { Composer } from "../components/Composer";
import { Badge, Card, EmptyState } from "../design/components/Display";
import { isBusy } from "../hooks/session";
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
  const navigate = useNavigate();
  const [question, setQuestion] = useState("");
  const box = useRef<HTMLTextAreaElement>(null);

  const ask = (text: string, language: UiLanguage) => {
    void submit(text, language);
    navigate("/ask");
  };
  const startWith = (act: string) => {
    if (!question.trim()) setQuestion(`${act}: `);
    box.current?.focus();
  };

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
      <div className="flex min-w-0 flex-col gap-6">
        <section className="rounded-lg border border-line-subtle bg-surface p-4 shadow-raised sm:p-6">
          <PageTitle className="text-balance">{t("hero_title")}</PageTitle>
          <p className="mt-2 mb-5 text-lg text-ink-muted">{t("hero_body")}</p>
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

        <section aria-labelledby="topics-title">
          <h2 id="topics-title" className="font-display-style text-2xl text-ink">
            {t("topics_title")}
          </h2>
          <p className="mt-1 mb-3 text-ink-muted">{t("topics_hint")}</p>
          <ul className="grid gap-3 sm:grid-cols-2">
            {TOPICS.map((topic) => {
              const act = t(`act_${topic}` as StringKey);
              return (
                <li key={topic}>
                  <button
                    type="button"
                    onClick={() => startWith(act)}
                    className="target flex h-full w-full cursor-pointer flex-col items-start gap-1 rounded-md border border-line-subtle bg-surface p-3 text-left motion-colors hover:border-line hover:bg-raised"
                  >
                    <span className="flex items-center gap-2 font-semibold text-ink">
                      <BookOpen aria-hidden="true" size={18} className="shrink-0 text-brand" />
                      {act}
                    </span>
                    <span className="text-sm text-ink-muted">{t(`domain_${topic}` as StringKey)}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        </section>
      </div>

      <div className="flex flex-col gap-6">
        <Card title={t("continue_title")}>
          {state.phase === "idle" ? (
            <EmptyState icon={<MessageSquare size={28} />} title={t("continue_empty_title")}>
              {t("continue_empty_body")}
            </EmptyState>
          ) : (
            <Link to="/ask" className="-mx-2 flex items-start gap-3 rounded-md px-2 py-2 text-ink hover:bg-sunken">
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
          <EmptyState icon={<Sun size={28} />} title={t("today_empty_title")}>
            {t("today_empty_body")}
          </EmptyState>
        </Card>
      </div>
    </div>
  );
}
