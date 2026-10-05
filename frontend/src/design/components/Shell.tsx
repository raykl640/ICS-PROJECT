import { PanelLeftClose, PanelLeftOpen, Search } from "lucide-react";
import type { ReactNode } from "react";
import { cx } from "../cx";
import { useMediaQuery } from "../useTheme";
import { IconButton } from "./Button";
import { Dialog, DialogContent } from "./Dialog";
import { Kbd } from "./Display";
import { Tooltip } from "./Overlay";

export interface NavItem {
  id: string;
  label: string;
  icon: ReactNode;
  href: string;
  current?: boolean;
  /** Also shown in the bottom bar on narrow screens. */
  primary?: boolean;
}

interface SidebarProps {
  /** Landmark name of the navigation. */
  label: string;
  items: NavItem[];
  collapsed: boolean;
  onCollapsedChange: (collapsed: boolean) => void;
  collapseLabel: string;
  expandLabel: string;
  brand?: ReactNode;
}

/** App navigation: left column from 768 px (collapsible to icons), bottom bar of primary items below. */
export function Sidebar({
  label,
  items,
  collapsed,
  onCollapsedChange,
  collapseLabel,
  expandLabel,
  brand,
}: SidebarProps) {
  // Narrow: last in the page flow and sticky to the bottom. Wide: a full-height column whose inner nav is sticky.
  return (
    <div
      className={cx(
        "sticky bottom-0 z-30 order-last border-t border-line-subtle bg-surface",
        "md:static md:order-none md:shrink-0 md:border-t-0 md:border-r",
        collapsed ? "md:w-[4.75rem]" : "md:w-60",
      )}
    >
      <nav aria-label={label} className="md:sticky md:top-0 md:flex md:h-dvh md:flex-col md:p-3">
        <div
          className={cx(
            "mb-4 hidden items-center gap-2 md:flex",
            collapsed ? "justify-center" : "justify-between pl-2",
          )}
        >
          {!collapsed && brand}
          <IconButton
            label={collapsed ? expandLabel : collapseLabel}
            aria-expanded={!collapsed}
            icon={collapsed ? <PanelLeftOpen size={20} /> : <PanelLeftClose size={20} />}
            onClick={() => onCollapsedChange(!collapsed)}
          />
        </div>
        <ul className="flex justify-around md:flex-col md:justify-start md:gap-1">
          {items.map((item) => {
            const link = (
              <a
                href={item.href}
                aria-current={item.current ? "page" : undefined}
                className={cx(
                  "target flex flex-col items-center justify-center gap-0.5 rounded-md px-2 py-1 text-xs font-semibold motion-colors",
                  "md:flex-row md:justify-start md:gap-3 md:px-3 md:text-base",
                  collapsed && "md:justify-center md:px-0",
                  item.current
                    ? "bg-sunken text-brand md:shadow-[inset_3px_0_0_var(--hk-brand)]"
                    : "text-ink-muted hover:bg-sunken hover:text-ink",
                )}
              >
                <span aria-hidden="true" className="inline-flex">
                  {item.icon}
                </span>
                <span className={cx(collapsed && "md:sr-only")}>{item.label}</span>
              </a>
            );
            return (
              <li key={item.id} className={cx(!item.primary && "hidden md:block")}>
                {collapsed ? (
                  <Tooltip label={item.label} side="right">
                    {link}
                  </Tooltip>
                ) : (
                  link
                )}
              </li>
            );
          })}
        </ul>
      </nav>
    </div>
  );
}

interface TopBarProps {
  start?: ReactNode;
  search?: { label: string; shortcut: string; onOpen: () => void };
  end?: ReactNode;
}

/** Page header: context on the left, global search (opens the command palette), account actions on the right. */
export function TopBar({ start, search, end }: TopBarProps) {
  return (
    <header className="sticky top-0 z-20 flex h-16 items-center gap-3 border-b border-line-subtle bg-canvas px-4 sm:px-6">
      <div className="min-w-0 flex-1 truncate">{start}</div>
      {search && (
        <button
          type="button"
          onClick={search.onOpen}
          className="target inline-flex cursor-pointer items-center gap-2 rounded-md border border-line bg-surface px-3 text-ink-muted motion-colors hover:text-ink sm:w-72"
        >
          <Search aria-hidden="true" size={18} />
          <span className="sr-only flex-1 text-left sm:not-sr-only">{search.label}</span>
          <span className="hidden sm:inline-flex">
            <Kbd>{search.shortcut}</Kbd>
          </span>
        </button>
      )}
      {end && <div className="flex items-center gap-1">{end}</div>}
    </header>
  );
}

interface SplitViewProps {
  main: ReactNode;
  aside: ReactNode;
  /** Name of the side panel (its heading and landmark name). */
  asideTitle: string;
  asideOpen: boolean;
  onAsideOpenChange: (open: boolean) => void;
  closeLabel: string;
}

/** Main content with a side panel: inline column from 1024 px, bottom sheet below. */
export function SplitView({ main, aside, asideTitle, asideOpen, onAsideOpenChange, closeLabel }: SplitViewProps) {
  const wide = useMediaQuery("(min-width: 1024px)");
  if (!wide) {
    return (
      <>
        {main}
        <Dialog open={asideOpen} onOpenChange={onAsideOpenChange}>
          <DialogContent title={asideTitle} closeLabel={closeLabel} side="bottom">
            {aside}
          </DialogContent>
        </Dialog>
      </>
    );
  }
  return (
    <div className={cx("grid gap-6", asideOpen && "grid-cols-[minmax(0,1fr)_minmax(20rem,26rem)]")}>
      <div className="min-w-0">{main}</div>
      {asideOpen && (
        <aside
          aria-label={asideTitle}
          className="sticky top-20 flex max-h-[calc(100dvh-6rem)] flex-col self-start rounded-lg border border-line-subtle bg-surface"
        >
          <div className="flex items-center justify-between gap-2 border-b border-line-subtle py-1 pr-1 pl-4">
            <h2 className="font-display-style text-lg text-ink">{asideTitle}</h2>
            <IconButton
              label={closeLabel}
              icon={<PanelLeftClose size={20} className="rotate-180" />}
              onClick={() => onAsideOpenChange(false)}
            />
          </div>
          <div className="min-h-0 overflow-y-auto p-3">{aside}</div>
        </aside>
      )}
    </div>
  );
}
