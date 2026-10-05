import { Check, Circle, CircleDot } from "lucide-react";
import { cx } from "../cx";

export type StepStatus = "done" | "current" | "todo";

const ICONS = { done: Check, current: CircleDot, todo: Circle } as const;
const TONES = { done: "text-success", current: "text-brand", todo: "text-ink-muted" } as const;

interface ProgressStepsProps {
  /** Accessible name of the list, e.g. "Answer progress". */
  label: string;
  steps: { label: string; status: StepStatus; detail?: string }[];
  /** Read out after each step label, e.g. { done: "done", current: "in progress", todo: "waiting" }. */
  statusText: Record<StepStatus, string>;
  orientation?: "vertical" | "horizontal";
}

/** Ordered steps of a long background job; the current step carries aria-current="step". */
export function ProgressSteps({ label, steps, statusText, orientation = "vertical" }: ProgressStepsProps) {
  return (
    <ol
      aria-label={label}
      className={cx("flex gap-3", orientation === "vertical" ? "flex-col" : "flex-row flex-wrap items-center")}
    >
      {steps.map((step) => {
        const Icon = ICONS[step.status];
        return (
          <li
            key={step.label}
            aria-current={step.status === "current" ? "step" : undefined}
            className="flex items-start gap-2"
          >
            <Icon aria-hidden="true" size={18} className={cx("mt-0.5 shrink-0", TONES[step.status])} />
            <span className="min-w-0">
              <span
                className={cx(
                  step.status === "todo" ? "text-ink-muted" : "text-ink",
                  step.status === "current" && "font-semibold",
                )}
              >
                {step.label}
              </span>
              <span className="sr-only">, {statusText[step.status]}</span>
              {step.detail && <span className="block text-sm text-ink-muted">{step.detail}</span>}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
