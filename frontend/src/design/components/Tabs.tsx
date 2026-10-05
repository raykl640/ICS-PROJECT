import * as RT from "@radix-ui/react-tabs";
import type { ComponentProps } from "react";
import { cx } from "../cx";

export const Tabs = RT.Root;

/** Underlined tabs on a hairline (arrow keys move between tabs, Home/End jump). `fit`: equal columns below 640 px. */
export function TabsList({ className, fit, ...props }: ComponentProps<typeof RT.List> & { fit?: boolean }) {
  return (
    <RT.List
      className={cx(
        "gap-6 border-b border-line-subtle max-sm:gap-1",
        fit ? "grid auto-cols-fr grid-flow-col sm:flex" : "flex overflow-x-auto",
        className,
      )}
      {...props}
    />
  );
}

/** One tab; the active one is ink with a brand underline (not colour alone: the underline marks it). */
export function TabsTrigger({ className, ...props }: ComponentProps<typeof RT.Trigger>) {
  return (
    <RT.Trigger
      className={cx(
        "target -mb-px inline-flex shrink-0 cursor-pointer items-center gap-2 border-b-2 border-transparent px-0.5 font-semibold",
        "text-center leading-tight text-ink-muted motion-colors hover:text-ink sm:whitespace-nowrap",
        "max-sm:flex-col max-sm:justify-center max-sm:gap-1 max-sm:px-1 max-sm:py-2 max-sm:text-sm",
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
