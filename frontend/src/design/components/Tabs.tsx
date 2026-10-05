import * as RT from "@radix-ui/react-tabs";
import type { ComponentProps } from "react";
import { cx } from "../cx";

export const Tabs = RT.Root;

/** Tab row (arrow keys move between tabs, Home/End jump). `fit`: equal columns with wrapping labels below 640 px. */
export function TabsList({ className, fit, ...props }: ComponentProps<typeof RT.List> & { fit?: boolean }) {
  return (
    <RT.List
      className={cx(
        "gap-1 border-b border-line-subtle",
        fit ? "grid auto-cols-fr grid-flow-col sm:flex" : "flex overflow-x-auto",
        className,
      )}
      {...props}
    />
  );
}

/** One tab; the active tab carries a brand underline, not colour alone. */
export function TabsTrigger({ className, ...props }: ComponentProps<typeof RT.Trigger>) {
  return (
    <RT.Trigger
      className={cx(
        "target -mb-px inline-flex shrink-0 cursor-pointer items-center gap-2 border-b-2 border-transparent px-3 font-semibold",
        "text-center leading-tight text-ink-muted motion-colors hover:text-ink sm:whitespace-nowrap",
        "max-sm:flex-col max-sm:gap-1 max-sm:px-1.5 max-sm:py-2 max-sm:text-sm",
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
