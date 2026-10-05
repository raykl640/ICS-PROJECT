import type { ComponentProps, ReactNode } from "react";
import { cx } from "../cx";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

const VARIANTS: Record<ButtonVariant, string> = {
  primary: "border-brand bg-brand text-brand-ink hover:bg-brand/90",
  secondary: "border-line bg-surface text-ink hover:bg-sunken",
  ghost: "border-transparent bg-transparent text-ink hover:bg-sunken",
  danger: "border-danger bg-surface text-danger hover:bg-sunken",
};

const BASE =
  "target inline-flex shrink-0 cursor-pointer items-center justify-center gap-2 rounded-md border font-semibold " +
  "motion-colors disabled:cursor-not-allowed disabled:opacity-55";

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
