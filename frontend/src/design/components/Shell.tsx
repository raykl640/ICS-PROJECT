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
}

interface MastheadProps {
  /** Landmark name of the navigation. */
  label: string;
  items: NavItem[];
  /** Full brand (top bar on phones) and the compact mark (top of the rail). */
  brand: ReactNode;
  brandMark?: ReactNode;
  /** Name of the current page, shown in the top bar. */
  title?: ReactNode;
  search?: { label: string; shortcut: string; onOpen: () => void };
  /** Right of the search: language, settings, account. */
  end?: ReactNode;
  /** Renders each link; pass the router's link so navigation stays client-side (default: a plain anchor). */
  linkComponent?: ComponentType<ComponentProps<"a"> & { href: string }>;
}

/** Width of the navigation rail from 768 px; the page content is offset by it. */
export const RAIL_OFFSET = "md:pl-[5.5rem]";

/**
 * App frame: a dark navigation rail on the left from 768 px (a bottom tab bar below; one "Main" landmark either way),
 * and a slim top bar with the page name, search and account controls.
 */
export function Masthead({
  label,
  items,
  brand,
  brandMark,
  title,
  search,
  end,
  linkComponent: Link = PlainLink,
}: MastheadProps) {
  return (
    <>
      <nav
        aria-label={label}
        className={cx(
          "fixed inset-x-0 bottom-0 z-30 border-t-2 border-mast-muted/40 bg-mast text-mast-ink",
          "md:inset-y-0 md:right-auto md:flex md:w-[5.5rem] md:flex-col md:border-t-0",
        )}
      >
        {brandMark && <div className="hidden h-16 shrink-0 items-center justify-center md:flex">{brandMark}</div>}
        <ul className="flex w-full justify-around md:flex-col md:justify-start md:gap-1 md:px-2 md:pt-2">
          {items.map((item) => (
            <li key={item.id} className="min-w-0 flex-1 md:flex-none">
              <Link
                href={item.href}
                aria-current={item.current ? "page" : undefined}
                className={cx(
                  "target flex h-full flex-col items-center justify-center gap-1 rounded-sm px-1 py-1.5 text-center",
                  "text-[0.6875rem] leading-tight font-semibold motion-colors md:py-2.5",
                  item.current ? "bg-highlight text-ink" : "text-mast-muted hover:bg-mast-ink/10 hover:text-mast-ink",
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
      <header
        className={cx("sticky top-0 z-20 border-b border-line-subtle bg-canvas/95 backdrop-blur-sm", RAIL_OFFSET)}
      >
        <div className="mx-auto flex h-14 max-w-6xl items-center gap-3 px-4 sm:px-6">
          <div className="md:hidden">{brand}</div>
          {title && <div className="hidden min-w-0 truncate font-display-style text-xl text-ink md:block">{title}</div>}
          <div className="ml-auto flex items-center gap-1">
            {search && (
              <button
                type="button"
                onClick={search.onOpen}
                className="target inline-flex cursor-pointer items-center gap-2 rounded-sm border-2 border-line px-2.5 text-ink-muted motion-colors hover:border-ink hover:text-ink lg:w-64"
              >
                <Search aria-hidden="true" size={18} />
                <span className="sr-only lg:not-sr-only lg:flex-1 lg:truncate lg:text-left lg:text-sm lg:whitespace-nowrap">{search.label}</span>
                <span className="hidden lg:inline-flex">
                  <Kbd>{search.shortcut}</Kbd>
                </span>
              </button>
            )}
            {end}
          </div>
        </div>
      </header>
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
          className="sticky top-[4.5rem] flex max-h-[calc(100dvh-5.5rem)] flex-col self-start border-2 border-ink bg-surface"
        >
          <div className="flex items-center justify-between gap-2 border-b-[3px] border-ink py-1 pr-1 pl-4">
            <h2 className="font-display-style text-xl text-ink">{asideTitle}</h2>
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
