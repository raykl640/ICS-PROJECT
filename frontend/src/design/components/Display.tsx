import type { ComponentProps, ReactNode } from "react";
import { cx } from "../cx";

type Tone = "neutral" | "brand" | "accent" | "success" | "warn" | "danger" | "info";

const TONES: Record<Tone, string> = {
  neutral: "text-ink-muted",
  brand: "text-brand",
  accent: "text-accent",
  success: "text-success",
  warn: "text-warn",
  danger: "text-danger",
  info: "text-info",
};

/** Small status pill; colour is never the only signal, so the text must say it. */
export function Badge({ tone = "neutral", icon, children }: { tone?: Tone; icon?: ReactNode; children: ReactNode }) {
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1 rounded-full bg-sunken px-2 py-0.5 text-xs font-semibold whitespace-nowrap",
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
    <kbd className="rounded-sm border border-current px-1.5 py-0.5 font-mono text-xs font-medium whitespace-nowrap">
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
  // "surface" is an open section (no box; a hairline above it when it follows another); "raised" a white panel;
  // "sunken" a shaded one.
  const toneClass = {
    surface: "[section+&]:mt-2 [section+&]:border-t [section+&]:border-line-subtle [section+&]:pt-8",
    raised: "rounded-lg border border-line-subtle bg-raised p-5 shadow-raised sm:p-6",
    sunken: "rounded-lg bg-sunken p-5 sm:p-6",
  }[tone];
  return (
    <section className={cx(toneClass, className)} {...props}>
      {(eyebrow || title || actions) && (
        <header className="mb-3 flex items-start justify-between gap-3">
          <div className="min-w-0">
            {eyebrow && <p className="mb-1 text-sm font-semibold text-ink-muted">{eyebrow}</p>}
            {title && <Heading className="font-display-style text-xl text-ink">{title}</Heading>}
          </div>
          {actions && <div className="flex shrink-0 items-center gap-1">{actions}</div>}
        </header>
      )}
      {children}
    </section>
  );
}

/** "Nothing here yet" block: a muted icon, a line or two and an optional action. */
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
    <div className="flex flex-col items-start gap-2 py-6">
      <span aria-hidden="true" className="inline-flex text-ink-muted">
        {icon}
      </span>
      <h3 className="font-semibold text-ink">{title}</h3>
      {children && <p className="max-w-prose text-ink-muted">{children}</p>}
      {action}
    </div>
  );
}

const NOTICE_TONES = { info: "border-l-info", warn: "border-l-warn", danger: "border-l-danger" } as const;

/** A short notice; the tone is a coloured edge, the words carry the meaning. */
export function Notice({
  tone,
  title,
  children,
}: {
  tone: keyof typeof NOTICE_TONES;
  title?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <div className={cx("rounded-md border-l-4 bg-sunken/60 px-4 py-3 text-ink", NOTICE_TONES[tone])}>
      {title && <p className="font-semibold">{title}</p>}
      {children}
    </div>
  );
}
