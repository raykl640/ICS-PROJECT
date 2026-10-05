import type { ComponentProps, ReactNode } from "react";
import { cx } from "../cx";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./Tabs";

interface AnswerCardProps {
  /** The card heading (the question is shown above the card). */
  title: ReactNode;
  /** Right of the heading, e.g. the live status line. */
  meta?: ReactNode;
  /** Between the heading and the tabs, e.g. progress steps while the answer is written. */
  status?: ReactNode;
  tabs: { id: string; label: ReactNode; content: ReactNode }[];
  value: string;
  onValueChange: (id: string) => void;
  /** Marks the tab panels aria-busy while text is still arriving. */
  busy?: boolean;
  /** Below the tabs, e.g. warnings once the answer is complete. */
  notes?: ReactNode;
  actions?: ReactNode;
  /** Always rendered: the "legal information, not legal advice" disclaimer goes here. */
  footer: ReactNode;
  className?: string;
}

/** One answer: heading, status, What the law says / What you can do / Draft letter tabs, actions and disclaimer. */
export function AnswerCard({
  title,
  meta,
  status,
  tabs,
  value,
  onValueChange,
  busy,
  notes,
  actions,
  footer,
  className,
}: AnswerCardProps) {
  return (
    <article className={cx("rounded-lg border border-line-subtle bg-surface shadow-raised", className)}>
      <header className="flex flex-wrap items-baseline justify-between gap-2 px-4 pt-4 sm:px-5">
        <h2 className="min-w-0 font-display-style text-xl text-ink">{title}</h2>
        {meta}
      </header>
      {status && <div className="px-4 pt-3 sm:px-5">{status}</div>}
      <Tabs value={value} onValueChange={onValueChange} className="px-4 pb-4 sm:px-5">
        <TabsList fit className="mt-3">
          {tabs.map((t) => (
            <TabsTrigger key={t.id} value={t.id}>
              {t.label}
            </TabsTrigger>
          ))}
        </TabsList>
        {tabs.map((t) => (
          <TabsContent key={t.id} value={t.id} aria-busy={busy} className="text-[1.0625rem] leading-relaxed text-ink">
            {t.content}
          </TabsContent>
        ))}
      </Tabs>
      {notes && <div className="flex flex-col gap-3 border-t border-line-subtle px-4 py-4 sm:px-5">{notes}</div>}
      {actions && <div className="flex flex-wrap gap-2 border-t border-line-subtle px-4 py-3 sm:px-5">{actions}</div>}
      <footer className="rounded-b-lg border-t border-line-subtle bg-sunken px-4 py-3 text-sm text-ink-muted sm:px-5">
        {footer}
      </footer>
    </article>
  );
}

interface SourceCardProps {
  id: string;
  act: string;
  /** e.g. "Section 4 — Reasons for ending a job". */
  heading: string;
  /** Short margin mark, e.g. "s. 4". */
  mark: string;
  /** e.g. "Part II · Page 3". */
  locator: string;
  /** Accessible name of the scrollable text region. */
  regionLabel: string;
  /** Shown under the locator, e.g. a "shortened" notice. */
  badge?: ReactNode;
  /** Highlighted after a citation jump. */
  highlighted?: boolean;
  /** The verbatim provision text (line breaks kept). */
  children: string;
}

/** One retrieved provision, verbatim in the reading face; focusable so a citation jump can land on it. */
export function SourceCard({
  id,
  act,
  heading,
  mark,
  locator,
  regionLabel,
  badge,
  highlighted,
  children,
}: SourceCardProps) {
  return (
    <article
      id={id}
      tabIndex={-1}
      aria-label={`${act}, ${heading}`}
      data-highlighted={highlighted ? "true" : "false"}
      className={cx(
        "scroll-mt-4 rounded-md border bg-raised motion-colors",
        highlighted ? "border-focus outline-2 outline-offset-2 outline-focus" : "border-line-subtle",
      )}
    >
      <header className="flex gap-3 border-b border-line-subtle px-4 py-3">
        <span aria-hidden="true" className="w-12 shrink-0 pt-0.5 font-display-style text-lg leading-tight text-brand">
          {mark}
        </span>
        <div className="min-w-0">
          <p className="text-sm font-semibold text-ink-muted">{act}</p>
          <h3 className="font-display-style text-lg leading-snug text-ink">{heading}</h3>
          <p className="text-sm text-ink-muted">{locator}</p>
          {badge && <div className="mt-2">{badge}</div>}
        </div>
      </header>
      <div
        role="region"
        tabIndex={0}
        aria-label={regionLabel}
        className={cx("max-h-96 overflow-y-auto px-4 py-3", highlighted && "bg-highlight/40")}
      >
        <LawText size="sm" className="whitespace-pre-wrap">
          {children}
        </LawText>
      </div>
    </article>
  );
}

/** Statute-style reading text: reading face, generous leading, ~68 character measure. */
export function LawText({
  size = "md",
  className,
  children,
}: {
  size?: "sm" | "md";
  className?: string;
  children: ReactNode;
}) {
  return (
    <div
      className={cx(
        "law-text max-w-[68ch] font-reading text-ink",
        size === "md" ? "text-[1.0625rem] leading-[1.75]" : "text-[0.9375rem] leading-[1.65]",
        className,
      )}
    >
      {children}
    </div>
  );
}

/** Cross-reference inside law text (a real link, so it works with middle-click and the keyboard). */
export function LawRef({ className, ...props }: ComponentProps<"a">) {
  return (
    <a
      className={cx(
        "font-semibold text-brand underline decoration-accent decoration-2 underline-offset-3 hover:decoration-brand",
        className,
      )}
      {...props}
    />
  );
}
