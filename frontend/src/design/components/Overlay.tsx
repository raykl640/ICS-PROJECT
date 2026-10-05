import * as RP from "@radix-ui/react-popover";
import * as RSA from "@radix-ui/react-scroll-area";
import * as RTip from "@radix-ui/react-tooltip";
import type { ComponentProps, ReactElement, ReactNode } from "react";
import { cx } from "../cx";

export const TooltipProvider = RTip.Provider;

/** Short hint on hover and keyboard focus; never the only place information lives. */
export function Tooltip({
  label,
  side = "top",
  children,
}: {
  label: string;
  side?: RTip.TooltipContentProps["side"];
  children: ReactElement;
}) {
  return (
    <RTip.Root>
      <RTip.Trigger asChild>{children}</RTip.Trigger>
      <RTip.Portal>
        <RTip.Content
          side={side}
          sideOffset={6}
          className="z-50 rounded-md bg-ink px-2 py-1 text-xs font-medium text-canvas"
        >
          {label}
        </RTip.Content>
      </RTip.Portal>
    </RTip.Root>
  );
}

export const Popover = RP.Root;
export const PopoverTrigger = RP.Trigger;
export const PopoverClose = RP.Close;

/** Non-modal popup anchored to its trigger (Escape closes, focus returns). */
export function PopoverContent({ className, sideOffset = 6, ...props }: ComponentProps<typeof RP.Content>) {
  return (
    <RP.Portal>
      <RP.Content
        sideOffset={sideOffset}
        className={cx(
          "z-50 w-[min(20rem,calc(100vw-2rem))] rounded-lg bg-raised p-4 text-ink shadow-overlay",
          className,
        )}
        {...props}
      />
    </RP.Portal>
  );
}

/** Scroll container with a thin themed scrollbar (native scrolling and keyboard behaviour kept). */
export function ScrollArea({
  className,
  children,
  label,
}: {
  className?: string;
  children: ReactNode;
  label?: string;
}) {
  return (
    <RSA.Root type="hover" className={cx("overflow-hidden", className)}>
      <RSA.Viewport className="h-full w-full" aria-label={label} tabIndex={label ? 0 : undefined}>
        {children}
      </RSA.Viewport>
      <RSA.Scrollbar orientation="vertical" className="flex w-2 touch-none p-0.5 select-none">
        <RSA.Thumb className="flex-1 bg-line" />
      </RSA.Scrollbar>
    </RSA.Root>
  );
}
