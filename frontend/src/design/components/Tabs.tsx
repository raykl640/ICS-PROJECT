import * as RT from "@radix-ui/react-tabs";
import type { ComponentProps } from "react";
import { cx } from "../cx";

export const Tabs = RT.Root;

/** Tab row (arrow keys move between tabs, Home/End jump; scrolls sideways on narrow screens). */
export function TabsList({ className, ...props }: ComponentProps<typeof RT.List>) {
  return <RT.List className={cx("flex gap-1 overflow-x-auto border-b border-line-subtle", className)} {...props} />;
}

/** One tab; the active tab carries a brand underline, not colour alone. */
export function TabsTrigger({ className, ...props }: ComponentProps<typeof RT.Trigger>) {
  return (
    <RT.Trigger
      className={cx(
        "target -mb-px inline-flex shrink-0 cursor-pointer items-center gap-2 border-b-2 border-transparent px-3 font-semibold",
        "whitespace-nowrap text-ink-muted motion-colors hover:text-ink",
        "data-[state=active]:border-brand data-[state=active]:text-ink",
        className,
      )}
      {...props}
    />
  );
}

/** Panel for one tab. */
export function TabsContent({ className, ...props }: ComponentProps<typeof RT.Content>) {
  return <RT.Content className={cx("pt-4", className)} {...props} />;
}
