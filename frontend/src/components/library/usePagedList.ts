// A cursor-paged list: the first page reloads with the library; "Show more" appends the next pages.
import { useState } from "react";
import type { Page } from "../../api/library";
import { useLibrary } from "../../app/contexts";
import { useLoad } from "../../hooks/useLoad";

export interface PagedList<T> {
  status: "loading" | "error" | "ok";
  items: T[];
  hasMore: boolean;
  loadingMore: boolean;
  loadMore: () => void;
}

/** Items of the list at key (a query string), fetched with fetchPage(cursor). */
export function usePagedList<T>(key: string, fetchPage: (cursor: string | null) => Promise<Page<T>>): PagedList<T> {
  const { version } = useLibrary();
  const { result } = useLoad(key, () => fetchPage(null));
  const scope = `${key}#${version}`;
  const [more, setMore] = useState<{ scope: string; items: T[]; cursor: string | null; busy: boolean } | null>(null);

  if (result.status !== "ok")
    return { status: result.status, items: [], hasMore: false, loadingMore: false, loadMore: () => {} };
  const extra = more?.scope === scope ? more : null;
  const cursor = extra ? extra.cursor : result.data.next_cursor;
  const loadMore = () => {
    if (!cursor || extra?.busy) return;
    const previous = extra?.items ?? [];
    setMore({ scope, items: previous, cursor, busy: true });
    fetchPage(cursor).then(
      (page) => setMore({ scope, items: [...previous, ...page.items], cursor: page.next_cursor, busy: false }),
      () => setMore({ scope, items: previous, cursor, busy: false }),
    );
  };
  return {
    status: "ok",
    items: [...result.data.items, ...(extra?.items ?? [])],
    hasMore: cursor !== null,
    loadingMore: extra?.busy ?? false,
    loadMore,
  };
}
