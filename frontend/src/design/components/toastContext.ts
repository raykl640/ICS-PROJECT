import { createContext, useContext } from "react";

export interface ToastInput {
  title: string;
  description?: string;
  tone?: "info" | "success" | "danger";
  /** One button in the toast (e.g. Undo, Open); it closes the toast. */
  action?: { label: string; onSelect: () => void };
  /** Milliseconds before it closes by itself (default 6000). */
  duration?: number;
}

export const ToastContext = createContext<((toast: ToastInput) => void) | null>(null);

/** Show a toast; requires a ToastProvider above. */
export function useToast(): (toast: ToastInput) => void {
  const show = useContext(ToastContext);
  if (!show) throw new Error("useToast needs a ToastProvider");
  return show;
}
