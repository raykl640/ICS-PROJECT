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

/** Small stamped status label (mono capitals); colour is never the only signal, so the text must say it. */
export function Badge({ tone = "neutral", icon, children }: { tone?: Tone; icon?: ReactNode; children: ReactNode }) {
  return (
    <span
      className={cx(
        "label-mono inline-flex items-center gap-1 rounded-sm border-[1.5px] px-1.5 py-0.5 font-semibold whitespace-nowrap",
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
    <kbd className="rounded-sm border border-current px-1.5 py-0.5 font-mono text-xs font-medium whitespace-nowrap opacity-80">
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
  // A sheet has a heavy rule on top and no box; "raised" is a boxed slip, "sunken" a shaded one.
  const toneClass = {
    surface: "border-t-[3px] border-ink pt-3",
    raised: "border border-ink bg-raised p-4 sm:p-5",
    sunken: "border-t-[3px] border-ink bg-sunken p-4 sm:p-5",
  }[tone];
  return (
    <section className={cx(toneClass, className)} {...props}>
      {(eyebrow || title || actions) && (
        <header className="mb-3 flex items-start justify-between gap-3">
          <div className="min-w-0">
            {eyebrow && <p className="label-mono mb-1 text-accent">{eyebrow}</p>}
            {title && <Heading className="font-display-style text-2xl text-ink">{title}</Heading>}
          </div>
          {actions && <div className="flex shrink-0 items-center gap-1">{actions}</div>}
        </header>
      )}
      {children}
    </section>
  );
}

/** "Nothing here yet" block, hatched like unused space on a form, with an optional action. */
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
    <div className="hatch flex flex-col items-start gap-2 border-y border-line-subtle px-4 py-6">
      <span aria-hidden="true" className="inline-flex text-ink-muted">
        {icon}
      </span>
      <h3 className="font-display-style text-xl text-ink">{title}</h3>
      {children && <p className="max-w-prose bg-canvas/80 text-ink-muted">{children}</p>}
      {action}
    </div>
  );
}

const NOTICE_TONES = { info: "border-l-info", warn: "border-l-warn", danger: "border-l-danger" } as const;

/** A notice slip; the tone is a thick coloured edge, the words carry the meaning. */
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
    <div
      className={cx(
        "rounded-sm border border-l-[6px] border-line-subtle bg-surface px-4 py-3 text-ink",
        NOTICE_TONES[tone],
      )}
    >
      {title && <p className="font-semibold">{title}</p>}
      {children}
    </div>
  );
}
