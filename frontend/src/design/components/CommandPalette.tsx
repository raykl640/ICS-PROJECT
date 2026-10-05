import * as RD from "@radix-ui/react-dialog";
import { Search } from "lucide-react";
import { useEffect, useId, useState, type KeyboardEvent, type ReactNode } from "react";
import { cx } from "../cx";

export interface CommandItem {
  id: string;
  label: string;
  group: string;
  hint?: string;
  icon?: ReactNode;
  onSelect: () => void;
}

interface CommandPaletteProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Dialog name (visually hidden) and input label. */
  title: string;
  placeholder: string;
  emptyText: string;
  items: CommandItem[];
  /** Commands built from the query itself (e.g. "Employment s.41"), listed first and not filtered. */
  dynamic?: (query: string) => CommandItem[];
  /** Commands built from the query, listed after the matching ones (e.g. "Search for …"). */
  fallback?: (query: string) => CommandItem[];
}

const matches = (item: CommandItem, query: string) =>
  `${item.label} ${item.hint ?? ""}`.toLowerCase().includes(query.trim().toLowerCase());

/** Ctrl/Cmd+K palette: a combobox over grouped commands (Up/Down move, Enter runs, Escape closes). */
export function CommandPalette({
  open,
  onOpenChange,
  title,
  placeholder,
  emptyText,
  items,
  dynamic,
  fallback,
}: CommandPaletteProps) {
  const base = useId();
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const shown = [
    ...(dynamic?.(query) ?? []),
    ...items.filter((item) => matches(item, query)),
    ...(fallback?.(query) ?? []),
  ];
  const groups = [...new Set(shown.map((item) => item.group))];
  const ordered = groups.flatMap((g) => shown.filter((item) => item.group === g));
  const activeItem = ordered[Math.min(active, ordered.length - 1)];
  const optionId = (item: CommandItem) => `${base}-option-${item.id}`;

  useEffect(() => {
    if (activeItem) document.getElementById(optionId(activeItem))?.scrollIntoView?.({ block: "nearest" });
  });

  const setOpen = (next: boolean) => {
    if (!next) {
      setQuery("");
      setActive(0);
    }
    onOpenChange(next);
  };
  const run = (item: CommandItem) => {
    setOpen(false);
    item.onSelect();
  };
  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (!ordered.length) return;
    const step = { ArrowDown: 1, ArrowUp: -1 }[event.key];
    if (step) {
      event.preventDefault();
      setActive((i) => (Math.min(i, ordered.length - 1) + step + ordered.length) % ordered.length);
    } else if (event.key === "Enter" && activeItem) {
      event.preventDefault();
      run(activeItem);
    }
  };

  return (
    <RD.Root open={open} onOpenChange={setOpen}>
      <RD.Portal>
        <RD.Overlay className="fixed inset-0 z-40 bg-scrim" />
        <RD.Content
          aria-describedby={undefined}
          className="fixed top-[10vh] left-1/2 z-50 flex max-h-[70vh] w-[min(40rem,calc(100vw-2rem))] -translate-x-1/2 flex-col overflow-hidden rounded-lg border border-line-subtle bg-raised text-ink shadow-overlay"
        >
          <RD.Title className="sr-only">{title}</RD.Title>
          <div className="flex items-center gap-2 border-b border-line-subtle px-4">
            <Search aria-hidden="true" size={20} className="shrink-0 text-ink-muted" />
            <input
              role="combobox"
              aria-label={title}
              aria-expanded="true"
              aria-controls={`${base}-list`}
              aria-autocomplete="list"
              aria-activedescendant={activeItem ? optionId(activeItem) : undefined}
              value={query}
              placeholder={placeholder}
              onChange={(e) => {
                setQuery(e.target.value);
                setActive(0);
              }}
              onKeyDown={onKeyDown}
              className="target w-full bg-transparent py-3 text-lg text-ink placeholder:text-ink-muted focus-visible:outline-none"
            />
          </div>
          <div id={`${base}-list`} role="listbox" aria-label={title} className="overflow-y-auto p-2">
            {ordered.length === 0 && <p className="px-3 py-6 text-center text-ink-muted">{emptyText}</p>}
            {groups.map((group) => (
              <div key={group} role="group" aria-labelledby={`${base}-group-${group}`}>
                <p id={`${base}-group-${group}`} className="px-3 pt-2 pb-1 text-sm font-semibold text-ink-muted">
                  {group}
                </p>
                {ordered
                  .filter((item) => item.group === group)
                  .map((item) => (
                    <div
                      key={item.id}
                      id={optionId(item)}
                      role="option"
                      aria-selected={item === activeItem}
                      onClick={() => run(item)}
                      onMouseMove={() => setActive(ordered.indexOf(item))}
                      className={cx(
                        "target flex cursor-pointer items-center gap-3 rounded-sm px-3",
                        item === activeItem && "bg-sunken",
                      )}
                    >
                      {item.icon && (
                        <span aria-hidden="true" className="inline-flex text-ink-muted">
                          {item.icon}
                        </span>
                      )}
                      <span className="min-w-0 flex-1 truncate">{item.label}</span>
                      {item.hint && <span className="text-sm text-ink-muted">{item.hint}</span>}
                    </div>
                  ))}
              </div>
            ))}
          </div>
        </RD.Content>
      </RD.Portal>
    </RD.Root>
  );
}
