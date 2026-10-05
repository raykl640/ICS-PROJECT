import type { ComponentProps, ReactNode } from "react";
import { cx } from "../cx";

type Tone = "neutral" | "brand" | "accent" | "success" | "warn" | "danger" | "info";

const TONES: Record<Tone, string> = {
  neutral: "border-line text-ink-muted",
  brand: "border-brand text-brand",
  accent: "border-accent text-accent",
  success: "border-success text-success",
  warn: "border-warn text-warn",
  danger: "border-danger text-danger",
  info: "border-info text-info",
};

/** Small outlined status label; colour is never the only signal, so the text must say it. */
export function Badge({ tone = "neutral", icon, children }: { tone?: Tone; icon?: ReactNode; children: ReactNode }) {
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1 rounded-sm border px-1.5 py-0.5 text-xs font-semibold whitespace-nowrap",
        TONES[tone],
      )}
    >
      {icon && (
        <span aria-hidden="true" className="inline-flex">
          {icon}
        </span>
      )}
      {children}
    </span>
  );
}

/** Keyboard key. */
export function Kbd({ children }: { children: ReactNode }) {
  return (
    <kbd className="rounded-sm border border-line bg-sunken px-1.5 py-0.5 font-ui text-xs font-semibold text-ink-muted">
      {children}
    </kbd>
  );
}

/** Static placeholder block (no shimmer: cheap on low-end CPUs and calm for reduced motion). */
export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden="true" className={cx("h-4 rounded-sm bg-sunken", className)} />;
}

type CardProps = Omit<ComponentProps<"section">, "title"> & {
  eyebrow?: ReactNode;
  title?: ReactNode;
  /** Heading level of the title (default 2). */
  level?: 2 | 3;
  actions?: ReactNode;
  tone?: "surface" | "raised" | "sunken";
};

/** Content container with an optional eyebrow, title and actions row. */
export function Card({
  eyebrow,
  title,
  level = 2,
  actions,
  tone = "surface",
  className,
  children,
  ...props
}: CardProps) {
  const Heading = level === 2 ? "h2" : "h3";
  const toneClass = { surface: "bg-surface", raised: "bg-raised shadow-raised", sunken: "bg-sunken" }[tone];
  return (
    <section className={cx("rounded-lg border border-line-subtle p-4 sm:p-5", toneClass, className)} {...props}>
      {(eyebrow || title || actions) && (
        <header className="mb-3 flex items-start justify-between gap-3">
          <div className="min-w-0">
            {eyebrow && <p className="mb-1 text-sm font-semibold text-accent">{eyebrow}</p>}
            {title && <Heading className="font-display-style text-xl text-ink">{title}</Heading>}
          </div>
          {actions && <div className="flex shrink-0 items-center gap-1">{actions}</div>}
        </header>
      )}
      {children}
    </section>
  );
}

/** Friendly "nothing here yet" block with an optional action. */
export function EmptyState({
  icon,
  title,
  children,
  action,
}: {
  icon: ReactNode;
  title: string;
  children?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed border-line px-6 py-10 text-center">
      <span aria-hidden="true" className="inline-flex text-ink-muted">
        {icon}
      </span>
      <h3 className="font-display-style text-lg text-ink">{title}</h3>
      {children && <p className="max-w-prose text-ink-muted">{children}</p>}
      {action}
    </div>
  );
}
