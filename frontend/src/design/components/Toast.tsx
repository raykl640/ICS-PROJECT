import * as RToast from "@radix-ui/react-toast";
import { CircleAlert, CircleCheck, Info, X } from "lucide-react";
import { useCallback, useRef, useState, type ReactNode } from "react";
import { cx } from "../cx";
import { ToastContext, type ToastInput } from "./toastContext";

const ICONS = { info: Info, success: CircleCheck, danger: CircleAlert } as const;
const TONES = { info: "text-info", success: "text-success", danger: "text-danger" } as const;

interface ToastProviderProps {
  /** Accessible name of the close button on each toast. */
  closeLabel: string;
  /** Landmark name of the toast region (Radix adds the F8 hotkey to reach it). */
  regionLabel: string;
  children: ReactNode;
}

/** Hosts toasts announced politely; each closes on its own, by swipe, Escape or its close button. */
export function ToastProvider({ closeLabel, regionLabel, children }: ToastProviderProps) {
  const [toasts, setToasts] = useState<(ToastInput & { id: number })[]>([]);
  const nextId = useRef(0);
  const show = useCallback((toast: ToastInput) => {
    const id = (nextId.current += 1);
    setToasts((all) => [...all, { ...toast, id }]);
  }, []);
  const drop = (id: number) => setToasts((all) => all.filter((t) => t.id !== id));

  return (
    <ToastContext.Provider value={show}>
      <RToast.Provider label={regionLabel} duration={6000}>
        {children}
        {toasts.map(({ id, title, description, tone = "info", action, duration }) => {
          const Icon = ICONS[tone];
          return (
            <RToast.Root
              key={id}
              duration={duration}
              onOpenChange={(open) => !open && drop(id)}
              className="flex items-start gap-3 rounded-md border border-line-subtle bg-raised p-3 text-ink shadow-overlay"
            >
              <Icon aria-hidden="true" size={20} className={cx("mt-0.5 shrink-0", TONES[tone])} />
              <div className="min-w-0 flex-1">
                <RToast.Title className="font-semibold">{title}</RToast.Title>
                {description && (
                  <RToast.Description className="text-sm text-ink-muted">{description}</RToast.Description>
                )}
                {action && (
                  <RToast.Action
                    altText={action.label}
                    onClick={action.onSelect}
                    className="target mt-2 cursor-pointer rounded-sm px-2 font-semibold text-brand underline underline-offset-3 hover:bg-sunken"
                  >
                    {action.label}
                  </RToast.Action>
                )}
              </div>
              <RToast.Close
                aria-label={closeLabel}
                className="target -m-2 inline-flex cursor-pointer items-center justify-center rounded-sm text-ink-muted hover:text-ink"
              >
                <X aria-hidden="true" size={18} />
              </RToast.Close>
            </RToast.Root>
          );
        })}
        <RToast.Viewport className="fixed right-0 bottom-16 z-50 flex w-full max-w-sm flex-col gap-2 p-4 outline-none md:bottom-0" />
      </RToast.Provider>
    </ToastContext.Provider>
  );
}
