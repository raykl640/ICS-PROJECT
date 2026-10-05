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
 * The stages of a long job as a row of ruled cells, the way a form tracks a filing: finished stages carry a solid
 * rule and a tick, the current one a rule of sliding hazard stripes, the rest a faint rule.
 * The current step carries aria-current="step".
 */
export function ProgressSteps({ label, steps, statusText }: ProgressStepsProps) {
  return (
    <ol aria-label={label} className="grid gap-x-3 gap-y-3 [counter-reset:step] sm:auto-cols-fr sm:grid-flow-col">
      {steps.map((step) => (
        <li
          key={step.label}
          aria-current={step.status === "current" ? "step" : undefined}
          className="flex flex-col gap-1.5 [counter-increment:step]"
        >
          <span
            aria-hidden="true"
            className={cx(
              "block h-1.5 w-full",
              step.status === "done" && "bg-ink",
              step.status === "current" && "tape",
              step.status === "todo" && "bg-line-subtle",
            )}
          />
          <span className="flex items-baseline gap-2">
            {step.status === "done" ? (
              <Check aria-hidden="true" size={14} className="shrink-0 self-center" />
            ) : (
              <span
                aria-hidden="true"
                className="font-mono text-xs text-ink-muted before:content-[counter(step,decimal-leading-zero)]"
              />
            )}
            <span
              className={cx(
                "font-semibold",
                step.status === "todo" ? "text-ink-muted" : "text-ink",
                step.status === "current" && "marker",
              )}
            >
              {step.label}
            </span>
            <span className="sr-only">, {statusText[step.status]}</span>
          </span>
          {step.detail && <span className="text-sm text-ink-muted">{step.detail}</span>}
        </li>
      ))}
    </ol>
  );
}
