import {
  ArrowRight,
  Bookmark,
  BookOpen,
  Briefcase,
  Car,
  Copy,
  FileText,
  House,
  ListTree,
  MessageSquare,
  NotebookPen,
  Shield,
  ShoppingBag,
  Sprout,
  ThumbsDown,
  ThumbsUp,
} from "lucide-react";
import { useState } from "react";
import { Button, IconButton } from "../components/Button";
import { Badge, Card, EmptyState, Skeleton } from "../components/Display";
import { TextArea } from "../components/Field";
import { AnswerCard, LawRef, LawText, SourceCard } from "../components/Legal";
import { Popover, PopoverContent, PopoverTrigger, Tooltip } from "../components/Overlay";
import { ProgressSteps } from "../components/ProgressSteps";
import { SplitView } from "../components/Shell";
import { ToggleGroup } from "../components/ToggleGroup";
import { cx } from "../cx";
import { AppFrame } from "./AppFrame";
import { CURRENT_SECTION, FAKE_ACT, FOLLOW_UP, LOREM, QUESTION, RECENT, SOURCES, TOC, TOPICS } from "./mockData";

const DISCLAIMER = "Legal information, not legal advice. Check the sources, and speak to an advocate before you act.";
const TOPIC_ICONS = [Briefcase, House, ShoppingBag, Shield, Sprout, Car];
const STATUS_TEXT = { done: "done", current: "in progress", todo: "waiting" };

/** Question composer with language choice. */
function Composer({ label, compact }: { label: string; compact?: boolean }) {
  const [lang, setLang] = useState<"en" | "sw">("en");
  const [text, setText] = useState("");
  return (
    <form className="flex flex-col gap-3" onSubmit={(e) => e.preventDefault()}>
      <TextArea
        label={label}
        hint={compact ? undefined : "Describe what happened in your own words. English or Kiswahili."}
        aside={`${text.length} / 2000`}
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder={LOREM[0]}
        className={compact ? "min-h-20" : undefined}
      />
      <div className="flex flex-wrap items-center justify-between gap-3">
        <ToggleGroup
          label="Answer language"
          value={lang}
          onValueChange={setLang}
          items={[
            { value: "en", label: "English" },
            { value: "sw", label: "Kiswahili" },
          ]}
        />
        <Button variant="primary" type="submit" icon={<ArrowRight size={18} />}>
          Ask
        </Button>
      </div>
    </form>
  );
}

/** Home: composer, knowledge of the day, continue list, topics, empty bookmarks. */
export function HomeMock() {
  return (
    <AppFrame screen="home" start={<span className="font-semibold text-ink">Home</span>}>
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="flex min-w-0 flex-col gap-6">
          <section
            aria-labelledby="ask-title"
            className="rounded-lg border border-line-subtle bg-surface p-4 shadow-raised sm:p-6"
          >
            <h1 id="ask-title" className="mb-1 font-display-style text-3xl text-ink">
              What do you need help with?
            </h1>
            <p className="mb-4 text-ink-muted">Answers come only from the Kenyan laws stored on this computer.</p>
            <Composer label="Your question" />
          </section>

          <Card
            eyebrow="Knowledge of the day"
            title="Lorem ipsum dolor sit amet"
            actions={<IconButton label="Bookmark" icon={<Bookmark size={20} />} />}
          >
            <div className="mb-3 flex flex-wrap gap-2">
              <Badge tone="accent">{FAKE_ACT}</Badge>
              <Badge tone="warn">Awaiting review</Badge>
            </div>
            <LawText>
              <p>{LOREM[0]}</p>
            </LawText>
            <p className="mt-3 text-ink-muted">{LOREM[1]}</p>
            <Button variant="ghost" className="mt-2 -ml-3 text-brand" icon={<BookOpen size={18} />}>
              Read the section
            </Button>
          </Card>

          <section aria-labelledby="topics-title">
            <h2 id="topics-title" className="mb-3 font-display-style text-xl text-ink">
              Life situations
            </h2>
            <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              {TOPICS.map((topic, i) => {
                const Icon = TOPIC_ICONS[i];
                return (
                  <li key={topic}>
                    <a
                      href="#topic"
                      className="target flex h-full flex-col gap-2 rounded-md border border-line-subtle bg-surface p-3 text-ink motion-colors hover:border-line"
                    >
                      <Icon aria-hidden="true" size={22} className="text-brand" />
                      <span className="font-semibold">{topic}</span>
                    </a>
                  </li>
                );
              })}
            </ul>
          </section>
        </div>

        <aside className="flex flex-col gap-6" aria-label="Continue">
          <Card title="Continue" level={2}>
            <ul className="-mx-2 flex flex-col">
              {RECENT.map((item) => (
                <li key={item.id}>
                  <a
                    href="#recent"
                    className="target flex items-start gap-3 rounded-md px-2 py-2 text-ink hover:bg-sunken"
                  >
                    {item.kind === "chat" ? (
                      <MessageSquare aria-hidden="true" size={20} className="mt-0.5 shrink-0 text-ink-muted" />
                    ) : (
                      <FileText aria-hidden="true" size={20} className="mt-0.5 shrink-0 text-ink-muted" />
                    )}
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-semibold">{item.title}</span>
                      <span className="text-sm text-ink-muted">
                        {item.kind === "chat" ? "Chat" : "Letter"} · {item.when}
                      </span>
                    </span>
                    <Badge tone={item.status === "Draft" ? "neutral" : "success"}>{item.status}</Badge>
                  </a>
                </li>
              ))}
            </ul>
          </Card>
          <EmptyState icon={<Bookmark size={28} />} title="No bookmarks yet">
            Bookmark a section while reading and it will appear here.
          </EmptyState>
        </aside>
      </div>
    </AppFrame>
  );
}

/** Answer body with inline citations (placeholder text). */
function RightsTab({ onCite }: { onCite: () => void }) {
  return (
    <div className="flex max-w-[68ch] flex-col gap-3">
      <p>
        {LOREM[0]}{" "}
        <LawRef
          href="#source-s1"
          onClick={(e) => {
            e.preventDefault();
            onCite();
          }}
        >
          Sample Act, s. 0.1
        </LawRef>
        .
      </p>
      <p>{LOREM[2]}</p>
      <ul className="ml-5 list-disc">
        <li>{LOREM[1]}</li>
        <li>{LOREM[3]}</li>
      </ul>
    </div>
  );
}

function UserBubble({ children }: { children: string }) {
  return (
    <p className="ml-auto max-w-[36rem] rounded-lg rounded-br-sm bg-sunken px-4 py-3 text-ink">
      <span className="sr-only">You asked: </span>
      {children}
    </p>
  );
}

/** Conversation: answered turn with tabs and sources, a follow-up still generating, follow-up composer. */
export function ConversationMock({ sourcesOpen }: { sourcesOpen?: boolean }) {
  const [open, setOpen] = useState(
    () => sourcesOpen ?? (typeof window.matchMedia === "function" && window.matchMedia("(min-width: 1024px)").matches),
  );
  const [highlight, setHighlight] = useState("s1");

  const sources = (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-ink-muted">Shown word for word, so you can check every claim.</p>
      {SOURCES.map((s) => (
        <SourceCard
          key={s.id}
          id={`source-${s.id}`}
          act={FAKE_ACT}
          locator={s.locator}
          highlighted={s.id === highlight}
        >
          {s.text.map((t) => (
            <p key={t}>{t}</p>
          ))}
        </SourceCard>
      ))}
    </div>
  );

  const main = (
    <div className="flex flex-col gap-5">
      <UserBubble>{QUESTION}</UserBubble>
      <AnswerCard
        question={<span className="sr-only">Answer</span>}
        meta={
          <>
            <Badge tone="neutral">English</Badge>
            <Badge tone="success">2 of 2 citations found in sources</Badge>
          </>
        }
        tabs={[
          {
            id: "rights",
            label: "What the law says",
            content: <RightsTab onCite={() => (setHighlight("s1"), setOpen(true))} />,
          },
          {
            id: "steps",
            label: "What you can do",
            content: (
              <ol className="ml-5 list-decimal">
                {LOREM.map((l) => (
                  <li key={l}>{l}</li>
                ))}
              </ol>
            ),
          },
          {
            id: "letter",
            label: "Draft letter",
            content: <pre className="font-reading whitespace-pre-wrap">{LOREM.join("\n\n")}</pre>,
          },
        ]}
        actions={
          <>
            <Button icon={<ListTree size={18} />} onClick={() => setOpen(true)}>
              Sources ({SOURCES.length})
            </Button>
            <Tooltip label="Copy answer">
              <IconButton label="Copy answer" icon={<Copy size={18} />} />
            </Tooltip>
            <span className="ml-auto flex gap-1">
              <IconButton label="Helpful" icon={<ThumbsUp size={18} />} />
              <IconButton label="Not helpful" icon={<ThumbsDown size={18} />} />
            </span>
          </>
        }
        footer={DISCLAIMER}
      />

      <UserBubble>{FOLLOW_UP}</UserBubble>
      <AnswerCard
        question={<span className="sr-only">Answer, still being written</span>}
        meta={<Badge tone="info">Working in the background</Badge>}
        tabs={[]}
        pending={
          <div className="grid gap-5 pt-3 sm:grid-cols-[minmax(0,15rem)_1fr]">
            <ProgressSteps
              label="Answer progress"
              statusText={STATUS_TEXT}
              steps={[
                { label: "Searching the laws", status: "done" },
                { label: "Reading 5 sections", status: "done" },
                {
                  label: "Writing the answer",
                  status: "current",
                  detail: "About 2 minutes left. You can leave this page.",
                },
                { label: "Checking citations", status: "todo" },
              ]}
            />
            <div className="flex flex-col gap-2.5" aria-hidden="true">
              <Skeleton className="w-11/12" />
              <Skeleton className="w-full" />
              <Skeleton className="w-4/5" />
              <Skeleton className="w-2/3" />
            </div>
          </div>
        }
        footer={DISCLAIMER}
      />

      <section aria-label="Ask a follow-up" className="rounded-lg border border-line-subtle bg-surface p-4">
        <Composer label="Ask a follow-up" compact />
      </section>
    </div>
  );

  return (
    <AppFrame
      screen="conversation"
      start={<span className="truncate font-semibold text-ink">Lorem ipsum conversation</span>}
    >
      <SplitView
        main={main}
        aside={sources}
        asideTitle="Sources"
        asideOpen={open}
        onAsideOpenChange={setOpen}
        closeLabel="Close sources"
      />
    </AppFrame>
  );
}

/** Table of contents for the placeholder Act. */
function Toc() {
  return (
    <nav aria-label="Contents">
      {TOC.map((part) => (
        <div key={part.part} className="mb-3">
          <p className="px-2 pb-1 text-sm font-semibold text-ink-muted">{part.part}</p>
          <ul>
            {part.sections.map((s) => (
              <li key={s}>
                <a
                  href="#section"
                  aria-current={s === CURRENT_SECTION ? "page" : undefined}
                  className={cx(
                    "target flex items-center rounded-sm px-2 text-ink",
                    s === CURRENT_SECTION ? "bg-sunken font-semibold text-brand" : "hover:bg-sunken",
                  )}
                >
                  {s}
                </a>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </nav>
  );
}

/** Law reader: contents, verbatim section text with a cross-reference, actions, cited-by and notes. */
export function ReaderMock() {
  return (
    <AppFrame
      screen="reader"
      start={
        <span className="text-ink-muted">
          Laws / <span className="font-semibold text-ink">{FAKE_ACT}</span>
        </span>
      }
    >
      <div className="grid gap-8 lg:grid-cols-[16rem_minmax(0,1fr)]">
        <aside className="hidden lg:block">
          <div className="sticky top-20">
            <Toc />
          </div>
        </aside>
        <article className="min-w-0">
          <div className="mb-4 lg:hidden">
            <Popover>
              <PopoverTrigger asChild>
                <Button icon={<ListTree size={18} />}>Contents</Button>
              </PopoverTrigger>
              <PopoverContent align="start" aria-label="Contents">
                <Toc />
              </PopoverContent>
            </Popover>
          </div>
          <p className="mb-1 text-sm font-semibold text-accent">Part II — Adipiscing elit</p>
          <h1 className="mb-3 font-display-style text-3xl text-ink">Section {CURRENT_SECTION}</h1>
          <div className="mb-5 flex flex-wrap items-center gap-2">
            <Badge tone="neutral">Page 0</Badge>
            <Badge tone="info">Cited by 2 sections</Badge>
          </div>
          <div className="mb-6 flex flex-wrap gap-2">
            <Button variant="primary" icon={<MessageSquare size={18} />}>
              Ask about this section
            </Button>
            <Button icon={<Bookmark size={18} />}>Bookmark</Button>
            <IconButton label="Add a note" variant="secondary" icon={<NotebookPen size={20} />} />
          </div>
          <LawText>
            <p>(1) {LOREM[0]}</p>
            <p>
              (2) {LOREM[1]} Subject to <LawRef href="#section">section 0.2</LawRef> of this placeholder Act,{" "}
              {LOREM[2].toLowerCase()}
            </p>
            <ol>
              <li>{LOREM[3]}</li>
              <li>{LOREM[0]}</li>
            </ol>
            <p>(3) {LOREM[2]}</p>
          </LawText>
          <div className="mt-8 grid gap-4 sm:grid-cols-2">
            <Card title="Cited by" level={2}>
              <ul className="flex flex-col gap-1">
                {["0.7 Ut enim ad minim", "0.8 Quis nostrud"].map((s) => (
                  <li key={s}>
                    <LawRef href="#section">Section {s}</LawRef>
                  </li>
                ))}
              </ul>
            </Card>
            <EmptyState icon={<NotebookPen size={26} />} title="No notes on this section">
              Notes stay on this computer.
            </EmptyState>
          </div>
        </article>
      </div>
    </AppFrame>
  );
}
