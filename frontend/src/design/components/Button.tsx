import type { ComponentProps, ReactNode } from "react";
import { cx } from "../cx";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger" | "mast";

// Primary sits on a ledge that it presses into, like a key; secondary and ghost fill with highlighter on hover.
const VARIANTS: Record<ButtonVariant, string> = {
  primary:
    "border-brand bg-brand text-brand-ink shadow-[0_3px_0_var(--hk-ink)] hover:border-ink hover:bg-ink hover:text-canvas " +
    "active:translate-y-[3px] active:shadow-none disabled:shadow-none",
  secondary: "border-ink bg-transparent text-ink hover:bg-highlight active:translate-y-px",
  ghost: "border-transparent bg-transparent text-ink hover:bg-highlight active:translate-y-px",
  danger: "border-danger bg-transparent text-danger hover:bg-danger hover:text-canvas active:translate-y-px",
  mast: "border-transparent bg-transparent text-mast-muted hover:bg-mast-ink hover:text-mast active:translate-y-px",
};

const BASE =
  "target inline-flex shrink-0 cursor-pointer items-center justify-center gap-2 rounded-sm border-2 font-semibold " +
  "motion-colors disabled:cursor-not-allowed disabled:opacity-50";

type ButtonProps = ComponentProps<"button"> & { variant?: ButtonVariant; icon?: ReactNode };

/** Text button (44 px minimum target); `icon` is decorative and sits before the label. */
export function Button({ variant = "secondary", icon, className, children, type = "button", ...props }: ButtonProps) {
  return (
    <button type={type} className={cx(BASE, "px-4 py-2", VARIANTS[variant], className)} {...props}>
      {icon && (
        <span aria-hidden="true" className="inline-flex">
          {icon}
        </span>
      )}
      {children}
    </button>
  );
}

type IconButtonProps = Omit<ComponentProps<"button">, "children"> & {
  /** Accessible name; icon-only buttons must always have one. */
  label: string;
  icon: ReactNode;
  variant?: ButtonVariant;
};

/** Square icon-only button with an accessible name. */
export function IconButton({ label, icon, variant = "ghost", className, type = "button", ...props }: IconButtonProps) {
  return (
    <button type={type} aria-label={label} className={cx(BASE, "p-2", VARIANTS[variant], className)} {...props}>
      <span aria-hidden="true" className="inline-flex">
        {icon}
      </span>
    </button>
  );
}

type ButtonLinkProps = ComponentProps<"a"> & { variant?: ButtonVariant; icon?: ReactNode };

/** A link styled as a button (downloads, navigation); same target size and variants. */
export function ButtonLink({ variant = "secondary", icon, className, children, ...props }: ButtonLinkProps) {
  return (
    <a className={cx(BASE, "px-4 py-2 no-underline", VARIANTS[variant], className)} {...props}>
      {icon && (
        <span aria-hidden="true" className="inline-flex">
          {icon}
        </span>
      )}
      {children}
    </a>
  );
}
