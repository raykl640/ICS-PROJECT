import * as RTG from "@radix-ui/react-toggle-group";
import type { ReactNode } from "react";
import { cx } from "../cx";

interface ToggleGroupProps<T extends string> {
  /** Accessible name of the group. */
  label: string;
  value: T;
  onValueChange: (value: T) => void;
  items: { value: T; label: string; icon?: ReactNode }[];
  /** Show only icons (labels become accessible names). */
  iconOnly?: boolean;
  /** "mast" for use on the dark masthead. */
  tone?: "default" | "mast";
  className?: string;
}

/** Segmented single choice (arrow keys move focus, Space/Enter picks); one item always stays selected. */
export function ToggleGroup<T extends string>({
  label,
  value,
  onValueChange,
  items,
  iconOnly,
  tone = "default",
  className,
}: ToggleGroupProps<T>) {
  const mast = tone === "mast";
  return (
    <RTG.Root
      type="single"
      aria-label={label}
      value={value}
      onValueChange={(next) => next && onValueChange(next as T)}
      className={cx("inline-flex gap-0.5 rounded-md p-0.5", mast ? "bg-mast-ink/10" : "bg-sunken", className)}
    >
      {items.map((item) => (
        <RTG.Item
          key={item.value}
          value={item.value}
          aria-label={iconOnly ? item.label : undefined}
          className={cx(
            "target inline-flex cursor-pointer items-center justify-center gap-1.5 rounded-[7px] px-3 font-semibold",
            "motion-colors data-[state=on]:shadow-raised",
            mast
              ? "text-mast-muted hover:text-mast-ink data-[state=on]:bg-raised data-[state=on]:text-ink"
              : "text-ink-muted hover:text-ink data-[state=on]:bg-raised data-[state=on]:text-ink",
          )}
        >
          {item.icon && (
            <span aria-hidden="true" className="inline-flex">
              {item.icon}
            </span>
          )}
          {!iconOnly && item.label}
        </RTG.Item>
      ))}
    </RTG.Root>
  );
}
