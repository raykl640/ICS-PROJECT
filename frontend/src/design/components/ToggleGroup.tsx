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
  className?: string;
}

/** Segmented single choice (arrow keys move focus, Space/Enter picks); one item always stays selected. */
export function ToggleGroup<T extends string>({
  label,
  value,
  onValueChange,
  items,
  iconOnly,
  className,
}: ToggleGroupProps<T>) {
  return (
    <RTG.Root
      type="single"
      aria-label={label}
      value={value}
      onValueChange={(next) => next && onValueChange(next as T)}
      className={cx("inline-flex rounded-md border border-line bg-surface p-0.5", className)}
    >
      {items.map((item) => (
        <RTG.Item
          key={item.value}
          value={item.value}
          aria-label={iconOnly ? item.label : undefined}
          className={cx(
            "target inline-flex cursor-pointer items-center justify-center gap-1.5 rounded-sm px-3 font-semibold",
            "text-ink-muted motion-colors hover:text-ink",
            "data-[state=on]:bg-brand data-[state=on]:text-brand-ink",
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
