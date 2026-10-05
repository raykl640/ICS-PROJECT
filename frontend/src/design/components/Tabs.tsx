import * as RT from "@radix-ui/react-tabs";
import type { ComponentProps } from "react";
import { cx } from "../cx";

export const Tabs = RT.Root;

/** Index tabs on a ruled line (arrow keys move between tabs, Home/End jump). `fit`: equal columns below 640 px. */
export function TabsList({ className, fit, ...props }: ComponentProps<typeof RT.List> & { fit?: boolean }) {
  return (
    <RT.List
      className={cx(
        "gap-1 border-b-[3px] border-ink",
        fit ? "grid auto-cols-fr grid-flow-col sm:flex" : "flex overflow-x-auto",
        className,
      )}
      {...props}
    />
  );
}

/** One tab; the active one is a filled index tab joined to the page, so colour is never the only signal. */
export function TabsTrigger({ className, ...props }: ComponentProps<typeof RT.Trigger>) {
  return (
    <RT.Trigger
      className={cx(
        "target inline-flex shrink-0 cursor-pointer items-center gap-2 rounded-t-sm border-2 border-b-0 border-transparent px-4 font-semibold",
        "text-center leading-tight text-ink-muted motion-colors hover:bg-highlight hover:text-ink sm:whitespace-nowrap",
        "max-sm:flex-col max-sm:gap-1 max-sm:px-1.5 max-sm:py-2 max-sm:text-sm",
        "data-[state=active]:border-ink data-[state=active]:bg-ink data-[state=active]:text-canvas",
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
