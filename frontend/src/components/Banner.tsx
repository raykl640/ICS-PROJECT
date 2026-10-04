import type { ReactNode } from "react";

const TONES = {
  info: "border-line bg-sunken text-ink",
  warn: "border-warn-line bg-warn-bg text-warn-ink",
  danger: "border-danger-line bg-danger-bg text-danger-ink",
} as const;

/** A bordered notice block. */
export function Banner({ tone, title, children }: { tone: keyof typeof TONES; title?: string; children?: ReactNode }) {
  return (
    <div className={`rounded-lg border-l-4 border px-4 py-3 text-base leading-relaxed ${TONES[tone]}`}>
      {title && <p className="font-semibold">{title}</p>}
      {children}
    </div>
  );
}
