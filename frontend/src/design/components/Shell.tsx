import { PanelLeftClose, Search } from "lucide-react";
import type { ComponentProps, ComponentType, ReactNode } from "react";
import { cx } from "../cx";
import { useMediaQuery } from "../useMediaQuery";
import { IconButton } from "./Button";
import { Dialog, DialogContent } from "./Dialog";
import { Kbd } from "./Display";

export interface NavItem {
  id: string;
  label: string;
  icon: ReactNode;
  href: string;
  current?: boolean;
  /** Starts the lower group of the sidebar (help and settings). */
  secondary?: boolean;
}

interface MastheadProps {
  /** Landmark name of the navigation. */
  label: string;
  items: NavItem[];
  brand: ReactNode;
  /** label is the accessible name; short is the visible text in the sidebar. */
  search?: { label: string; short: string; shortcut: string; onOpen: () => void };
  /** Language and account controls: the top bar on phones, the foot of the sidebar from 1024 px. */
  end?: ReactNode;
  /** Renders each link; pass the router's link so navigation stays client-side (default: a plain anchor). */
  linkComponent?: ComponentType<ComponentProps<"a"> & { href: string }>;
}

/** Width of the sidebar from 1024 px; the page content is offset by it. */
export const RAIL_OFFSET = "lg:pl-60";

/**
 * App frame. From 1024 px one quiet sidebar holds everything: brand, search, the pages, language and account.
 * Below that a slim top bar (brand, search, account) and a bottom tab bar. One "Main" landmark either way; the layout
 * is pure CSS so it needs no media query in script.
 */
export function Masthead({ label, items, brand, search, end, linkComponent: Link = PlainLink }: MastheadProps) {
  return (
    <>
      <div
        aria-hidden="true"
        className="fixed inset-y-0 left-0 hidden w-60 border-r border-line-subtle bg-mast lg:block"
      />
      <header className="sticky top-0 z-20 border-b border-line-subtle bg-canvas lg:fixed lg:inset-x-auto lg:left-0 lg:w-60 lg:border-0 lg:bg-transparent">
        <div className="flex h-14 items-center gap-2 px-4 lg:h-auto lg:flex-col lg:items-stretch lg:gap-4 lg:px-4 lg:pt-5">
          <div className="lg:px-2">{brand}</div>
          <div className="ml-auto flex items-center gap-1 lg:ml-0">
            {search && (
              <button
                type="button"
                onClick={search.onOpen}
                aria-label={search.label}
                className="target inline-flex flex-1 cursor-pointer items-center gap-2 rounded-md px-2.5 text-ink-muted motion-colors hover:bg-sunken hover:text-ink lg:border lg:border-line-subtle lg:bg-raised"
              >
                <Search aria-hidden="true" size={18} />
                <span aria-hidden="true" className="hidden flex-1 truncate text-left text-sm lg:inline">
                  {search.short}
                </span>
                <span aria-hidden="true" className="hidden lg:inline-flex">
                  <Kbd>{search.shortcut}</Kbd>
                </span>
              </button>
            )}
            <div className="flex items-center gap-1 lg:fixed lg:bottom-0 lg:left-0 lg:w-60 lg:flex-col lg:items-stretch lg:gap-3 lg:border-t lg:border-line-subtle lg:p-4">
              {end}
            </div>
          </div>
        </div>
      </header>
      <nav
        aria-label={label}
        className={cx(
          "fixed inset-x-0 bottom-0 z-30 border-t border-line-subtle bg-canvas",
          "lg:top-[7.75rem] lg:right-auto lg:bottom-auto lg:w-60 lg:border-0 lg:bg-transparent lg:px-4",
        )}
      >
        <ul className="flex w-full justify-around lg:flex-col lg:gap-0.5">
          {items.map((item) => (
            <li key={item.id} className={cx("min-w-0 flex-1 lg:flex-none", item.secondary && "lg:mt-6")}>
              <Link
                href={item.href}
                aria-current={item.current ? "page" : undefined}
                className={cx(
                  "target flex h-full flex-col items-center justify-center gap-1 px-1 py-1.5 text-center text-[0.6875rem] leading-tight font-semibold motion-colors",
                  "lg:flex-row lg:justify-start lg:gap-3 lg:rounded-md lg:px-3 lg:py-2 lg:text-left lg:text-[0.9375rem]",
                  item.current
                    ? "text-brand lg:bg-raised lg:text-ink lg:shadow-raised"
                    : "text-ink-muted hover:text-ink lg:hover:bg-sunken",
                )}
              >
                <span aria-hidden="true" className="inline-flex">
                  {item.icon}
                </span>
                <span>{item.label}</span>
              </Link>
            </li>
          ))}
        </ul>
      </nav>
    </>
  );
}

function PlainLink(props: ComponentProps<"a"> & { href: string }) {
  return <a {...props} />;
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

/** Main content with a side panel: inline column from 1280 px (beside the sidebar), bottom sheet below. */
export function SplitView({ main, aside, asideTitle, asideOpen, onAsideOpenChange, closeLabel }: SplitViewProps) {
  const wide = useMediaQuery("(min-width: 1280px)");
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
    <div className={cx("grid gap-10", asideOpen && "grid-cols-[minmax(0,1fr)_minmax(20rem,24rem)]")}>
      <div className="min-w-0">{main}</div>
      {asideOpen && (
        <aside aria-label={asideTitle} className="sticky top-6 flex max-h-[calc(100dvh-3rem)] flex-col self-start">
          <div className="flex items-center justify-between gap-2 pb-2">
            <h2 className="font-display-style text-lg text-ink">{asideTitle}</h2>
            <IconButton
              label={closeLabel}
              icon={<PanelLeftClose size={20} className="rotate-180" />}
              onClick={() => onAsideOpenChange(false)}
            />
          </div>
          <div className="-mr-2 min-h-0 overflow-y-auto pr-2">{aside}</div>
        </aside>
      )}
    </div>
  );
}
