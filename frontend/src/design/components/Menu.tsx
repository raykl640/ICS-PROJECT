import * as RM from "@radix-ui/react-dropdown-menu";
import type { ComponentProps, ReactNode } from "react";
import { cx } from "../cx";

export const Menu = RM.Root;
export const MenuTrigger = RM.Trigger;

const POPUP = "z-50 min-w-48 rounded-md border border-line-subtle bg-raised p-1 text-ink shadow-overlay";

/** Menu popup (arrow keys move and wrap, typeahead, Escape closes and returns focus). */
export function MenuContent({
  className,
  sideOffset = 6,
  align = "end",
  loop = true,
  ...props
}: ComponentProps<typeof RM.Content>) {
  return (
    <RM.Portal>
      <RM.Content sideOffset={sideOffset} align={align} loop={loop} className={cx(POPUP, className)} {...props} />
    </RM.Portal>
  );
}

type MenuItemProps = ComponentProps<typeof RM.Item> & { icon?: ReactNode; tone?: "default" | "danger" };

/** Menu item with an optional decorative icon. */
export function MenuItem({ icon, tone = "default", className, children, ...props }: MenuItemProps) {
  return (
    <RM.Item
      className={cx(
        "target flex cursor-pointer select-none items-center gap-2 rounded-sm px-3 outline-none",
        "data-[highlighted]:bg-sunken data-[disabled]:cursor-not-allowed data-[disabled]:opacity-55",
        tone === "danger" ? "text-danger" : "text-ink",
        className,
      )}
      {...props}
    >
      {icon && (
        <span aria-hidden="true" className="inline-flex text-ink-muted">
          {icon}
        </span>
      )}
      {children}
    </RM.Item>
  );
}

/** Divider between groups of menu items. */
export function MenuSeparator() {
  return <RM.Separator className="my-1 h-px bg-line-subtle" />;
}

/** Non-interactive group label. */
export function MenuLabel({ children }: { children: ReactNode }) {
  return <RM.Label className="px-3 py-1.5 text-sm font-semibold text-ink-muted">{children}</RM.Label>;
}
