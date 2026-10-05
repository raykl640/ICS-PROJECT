import type { ComponentProps, ReactNode } from "react";
import { cx } from "../cx";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./Tabs";

interface AnswerCardProps {
  /** The question this answer is for (the card's heading). */
  question: ReactNode;
  meta?: ReactNode;
  tabs: { id: string; label: string; content: ReactNode }[];
  value?: string;
  onValueChange?: (id: string) => void;
  /** While set, replaces the tabs (the answer is still being generated). */
  pending?: ReactNode;
  actions?: ReactNode;
  /** Always rendered: the "legal information, not legal advice" disclaimer goes here. */
  footer: ReactNode;
  className?: string;
}

/** One answer: question heading, Rights / Steps / Letter tabs (or a pending state), actions and disclaimer. */
export function AnswerCard({
  question,
  meta,
  tabs,
  value,
  onValueChange,
  pending,
  actions,
  footer,
  className,
}: AnswerCardProps) {
  return (
    <article className={cx("rounded-lg border border-line-subtle bg-surface shadow-raised", className)}>
      <header className="flex flex-wrap items-start justify-between gap-2 px-4 pt-4 sm:px-5">
        <h2 className="min-w-0 font-display-style text-xl text-ink">{question}</h2>
        {meta && <div className="flex flex-wrap items-center gap-2">{meta}</div>}
      </header>
      <div className="px-4 pb-4 sm:px-5">
        {pending ?? (
          <Tabs
            value={value}
            onValueChange={onValueChange}
            defaultValue={value === undefined ? tabs[0]?.id : undefined}
          >
            <TabsList className="mt-2">
              {tabs.map((t) => (
                <TabsTrigger key={t.id} value={t.id}>
                  {t.label}
                </TabsTrigger>
              ))}
            </TabsList>
            {tabs.map((t) => (
              <TabsContent key={t.id} value={t.id} className="leading-relaxed text-ink">
                {t.content}
              </TabsContent>
            ))}
          </Tabs>
        )}
      </div>
      {actions && <div className="flex flex-wrap gap-2 border-t border-line-subtle px-4 py-3 sm:px-5">{actions}</div>}
      <footer className="rounded-b-lg border-t border-line-subtle bg-sunken px-4 py-3 text-sm text-ink-muted sm:px-5">
        {footer}
      </footer>
    </article>
  );
}

interface SourceCardProps extends Omit<ComponentProps<"article">, "title"> {
  act: string;
  /** e.g. "Section 12 · page 4". */
  locator: string;
  /** Highlighted after a citation jump. */
  highlighted?: boolean;
  actions?: ReactNode;
  children: ReactNode;
}

/** One retrieved source, shown verbatim in the reading face. */
export function SourceCard({ act, locator, highlighted, actions, children, className, ...props }: SourceCardProps) {
  return (
    <article
      tabIndex={-1}
      className={cx(
        "rounded-md border bg-raised p-4",
        highlighted ? "border-focus outline-2 outline-offset-2 outline-focus" : "border-line-subtle",
        className,
      )}
      {...props}
    >
      <header className="mb-2 flex items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 className="font-semibold text-ink">{act}</h3>
          <p className="text-sm text-ink-muted">{locator}</p>
        </div>
        {actions}
      </header>
      <LawText size="sm">{children}</LawText>
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
