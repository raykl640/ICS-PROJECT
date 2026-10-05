import { useId, type ComponentProps, type ReactNode } from "react";
import { cx } from "../cx";

const CONTROL =
  "w-full rounded-md border border-line bg-raised px-3 py-2 text-ink placeholder:text-ink-muted motion-colors " +
  "hover:border-ink focus:border-brand aria-[invalid=true]:border-danger disabled:cursor-not-allowed disabled:opacity-55";

interface FrameProps {
  label: string;
  hint?: string;
  error?: string;
  /** Shown at the end of the label row, e.g. a character counter. */
  aside?: ReactNode;
  className?: string;
  children: (control: { id: string; "aria-describedby"?: string; "aria-invalid"?: true }) => ReactNode;
}

function Frame({ label, hint, error, aside, className, children }: FrameProps) {
  const id = useId();
  const hintId = hint ? `${id}-hint` : undefined;
  const errorId = error ? `${id}-error` : undefined;
  const describedBy = [hintId, errorId].filter(Boolean).join(" ") || undefined;
  return (
    <div className={cx("flex flex-col gap-1.5", className)}>
      <div className="flex items-baseline justify-between gap-3">
        <label htmlFor={id} className="text-[0.9375rem] font-bold text-ink">
          {label}
        </label>
        {aside && <span className="text-xs text-ink-muted">{aside}</span>}
      </div>
      {hint && (
        <p id={hintId} className="text-sm text-ink-muted">
          {hint}
        </p>
      )}
      {children({ id, "aria-describedby": describedBy, "aria-invalid": error ? true : undefined })}
      {error && (
        <p id={errorId} className="text-sm font-semibold text-danger">
          {error}
        </p>
      )}
    </div>
  );
}

type Common = { label: string; hint?: string; error?: string; aside?: ReactNode; frameClassName?: string };

/** Labelled single-line input with optional hint and error (wired through aria-describedby). */
export function Field({
  label,
  hint,
  error,
  aside,
  frameClassName,
  className,
  ...props
}: Common & ComponentProps<"input">) {
  return (
    <Frame label={label} hint={hint} error={error} aside={aside} className={frameClassName}>
      {(a11y) => <input {...props} {...a11y} className={cx(CONTROL, "target", className)} />}
    </Frame>
  );
}

/** Labelled multi-line input. */
export function TextArea({
  label,
  hint,
  error,
  aside,
  frameClassName,
  className,
  ...props
}: Common & ComponentProps<"textarea">) {
  return (
    <Frame label={label} hint={hint} error={error} aside={aside} className={frameClassName}>
      {(a11y) => (
        <textarea {...props} {...a11y} className={cx(CONTROL, "min-h-28 resize-y leading-relaxed", className)} />
      )}
    </Frame>
  );
}

type SelectProps = Common & ComponentProps<"select"> & { options: { value: string; label: string }[] };

/** Labelled native select (native keyboard and screen-reader behaviour on every platform). */
export function Select({ label, hint, error, aside, frameClassName, className, options, ...props }: SelectProps) {
  return (
    <Frame label={label} hint={hint} error={error} aside={aside} className={frameClassName}>
      {(a11y) => (
        <select {...props} {...a11y} className={cx(CONTROL, "target cursor-pointer", className)}>
          {options.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      )}
    </Frame>
  );
}

/** Labelled checkbox with a 44 px target. */
export function Checkbox({ label, className, ...props }: { label: ReactNode } & Omit<ComponentProps<"input">, "type">) {
  const id = useId();
  return (
    <div className={cx("flex items-center gap-3", className)}>
      <input id={id} type="checkbox" className="size-5 shrink-0 cursor-pointer accent-brand" {...props} />
      <label htmlFor={id} className="target flex cursor-pointer items-center text-ink">
        {label}
      </label>
    </div>
  );
}
