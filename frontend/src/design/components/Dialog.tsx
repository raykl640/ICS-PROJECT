import * as RD from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import type { ReactNode } from "react";
import { cx } from "../cx";
import { IconButton } from "./Button";

export const Dialog = RD.Root;
export const DialogTrigger = RD.Trigger;
export const DialogClose = RD.Close;

const SIDES = {
  center: "left-1/2 top-1/2 w-[min(36rem,calc(100vw-2rem))] max-h-[85vh] -translate-x-1/2 -translate-y-1/2 rounded-lg",
  right: "inset-y-0 right-0 w-[min(28rem,100vw)]",
  bottom: "inset-x-0 bottom-0 max-h-[85vh] rounded-t-lg",
} as const;

interface DialogContentProps {
  title: ReactNode;
  description?: ReactNode;
  /** Accessible name of the close button. */
  closeLabel: string;
  /** center: modal dialog; right/bottom: sheet (drawer). */
  side?: keyof typeof SIDES;
  hideTitle?: boolean;
  className?: string;
  children: ReactNode;
}

/** Modal dialog or sheet: focus trapped, Escape and the close button dismiss, focus returns to the trigger. */
export function DialogContent({
  title,
  description,
  closeLabel,
  side = "center",
  hideTitle,
  className,
  children,
}: DialogContentProps) {
  return (
    <RD.Portal>
      <RD.Overlay className="fixed inset-0 z-40 bg-scrim" />
      <RD.Content
        className={cx(
          "fixed z-50 flex flex-col overflow-hidden rounded-lg bg-raised text-ink shadow-overlay",
          SIDES[side],
          className,
        )}
        {...(description ? {} : { "aria-describedby": undefined })}
      >
        <div
          className={cx(
            "flex items-center justify-between gap-3 border-b border-line-subtle px-5 py-2",
            hideTitle && "absolute top-0 right-0 border-b-0",
          )}
        >
          <RD.Title className={cx("font-display-style text-2xl", hideTitle && "sr-only")}>{title}</RD.Title>
          <RD.Close asChild>
            <IconButton label={closeLabel} icon={<X size={20} />} />
          </RD.Close>
        </div>
        {description && <RD.Description className="px-5 pt-3 text-ink-muted">{description}</RD.Description>}
        <div className="min-h-0 flex-1 overflow-y-auto px-5 pt-4 pb-5">{children}</div>
      </RD.Content>
    </RD.Portal>
  );
}
