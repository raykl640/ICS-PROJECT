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
    <article className={cx("flex flex-col", className)}>
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="sr-only">{title}</h2>
        {meta}
      </header>
      {status && <div className="pb-4">{status}</div>}
      <Tabs value={value} onValueChange={onValueChange}>
        <TabsList fit>
          {tabs.map((t) => (
            <TabsTrigger key={t.id} value={t.id}>
              {t.label}
            </TabsTrigger>
          ))}
        </TabsList>
        {tabs.map((t) => (
          <TabsContent
            key={t.id}
            value={t.id}
            aria-busy={busy}
            className="pt-6 text-[1.125rem] leading-[1.75] text-ink"
          >
            {t.content}
          </TabsContent>
        ))}
      </Tabs>
      {notes && <div className="mt-6 flex flex-col gap-3">{notes}</div>}
      {actions && <div className="mt-6 flex flex-wrap gap-2">{actions}</div>}
      <footer className="mt-6 border-t border-line-subtle pt-4 text-[0.8125rem] leading-snug text-ink-muted">
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
  /** Changes on every citation click, so the highlighter sweeps again when the same citation is clicked twice. */
  pulse?: number;
  /** Buttons for this provision (e.g. Save section), under the locator. */
  actions?: ReactNode;
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
  pulse = 0,
  actions,
  children,
}: SourceCardProps) {
  return (
    <article
      id={id}
      tabIndex={-1}
      aria-label={`${act}, ${heading}`}
      data-highlighted={highlighted ? "true" : "false"}
      className={cx(
        "scroll-mt-4 rounded-lg border bg-raised motion-colors",
        highlighted ? "border-brand shadow-raised" : "border-line-subtle",
      )}
    >
      <header className="px-4 pt-3.5 pb-2">
        <p className="text-sm text-ink-muted">
          <span aria-hidden="true" className="mr-2 font-mono font-semibold text-brand">
            {mark}
          </span>
          {act}
        </p>
        <h3 className="mt-1 leading-snug font-semibold text-ink">{heading}</h3>
        <p className="mt-0.5 text-xs text-ink-muted">{locator}</p>
        {badge && <div className="mt-2">{badge}</div>}
        {actions && <div className="mt-2 -ml-3 flex flex-wrap gap-2">{actions}</div>}
      </header>
      <div
        role="region"
        tabIndex={0}
        aria-label={regionLabel}
        data-sweep={highlighted ? String(pulse % 2) : undefined}
        className={cx("max-h-80 overflow-y-auto rounded-b-lg px-4 pt-1 pb-4", highlighted && "sweep")}
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
      className={cx("font-semibold text-brand underline decoration-2 underline-offset-3 hover:text-ink", className)}
      {...props}
    />
  );
}
