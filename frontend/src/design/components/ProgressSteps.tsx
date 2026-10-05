import { Check } from "lucide-react";
import { cx } from "../cx";

export type StepStatus = "done" | "current" | "todo";

interface ProgressStepsProps {
  /** Accessible name of the list, e.g. "Answer progress". */
  label: string;
  steps: { label: string; status: StepStatus; detail?: string }[];
  /** Read out after each step label, e.g. { done: "done", current: "in progress", todo: "waiting" }. */
  statusText: Record<StepStatus, string>;
}

/**
 * The stages of a long job as thin segments: finished ones solid with a tick, the current one pulsing gently (still
 * when motion is reduced), the rest faint. The current step carries aria-current="step".
 */
export function ProgressSteps({ label, steps, statusText }: ProgressStepsProps) {
  return (
    <ol aria-label={label} className="grid gap-x-2 gap-y-3 sm:auto-cols-fr sm:grid-flow-col">
      {steps.map((step) => (
        <li
          key={step.label}
          aria-current={step.status === "current" ? "step" : undefined}
          className="flex flex-col gap-1.5"
        >
          <span
            aria-hidden="true"
            className={cx(
              "block h-1 w-full rounded-full",
              step.status === "done" && "bg-brand",
              step.status === "current" && "tape bg-brand/40",
              step.status === "todo" && "bg-line-subtle",
            )}
          />
          <span className="flex items-center gap-1.5 text-sm">
            {step.status === "done" && <Check aria-hidden="true" size={14} className="shrink-0 text-brand" />}
            <span className={cx(step.status === "todo" ? "text-ink-muted" : "font-semibold text-ink")}>
              {step.label}
            </span>
            <span className="sr-only">, {statusText[step.status]}</span>
          </span>
          {step.detail && <span className="text-xs text-ink-muted">{step.detail}</span>}
        </li>
      ))}
    </ol>
  );
}
