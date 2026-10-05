// Load data for a key (e.g. an id or a query string) and reload it when the library changes; keeps the last data
// while reloading so lists do not flash.
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { ApiError } from "../api/client";
import { useLibrary } from "../app/contexts";

export type Loaded<T> =
  { status: "loading" } | { status: "error"; notFound: boolean } | { status: "ok"; data: T; reloading: boolean };

interface Entry<T> {
  key: string;
  /** key, library version and reload count this entry was loaded for. */
  stamp: string;
  data?: T;
  failed?: { notFound: boolean };
}

/** The result of load() for key; key null means "nothing to load". reload() fetches again. */
export function useLoad<T>(key: string | null, load: () => Promise<T>): { result: Loaded<T>; reload: () => void } {
  const { version } = useLibrary();
  const loader = useRef(load);
  const [entry, setEntry] = useState<Entry<T> | null>(null);
  const [tick, setTick] = useState(0);

  useLayoutEffect(() => {
    loader.current = load;
  });

  useEffect(() => {
    if (key === null) return;
    let live = true;
    const stamp = `${key}#${version}#${tick}`;
    loader.current().then(
      (data) => {
        if (live) setEntry({ key, stamp, data });
      },
      (error: unknown) => {
        if (!live) return;
        setEntry((previous) =>
          previous?.key === key && previous.data !== undefined
            ? { ...previous, stamp }
            : { key, stamp, failed: { notFound: error instanceof ApiError && error.status === 404 } },
        );
      },
    );
    return () => {
      live = false;
    };
  }, [key, version, tick]);

  const reload = useCallback(() => setTick((n) => n + 1), []);
  if (key === null || entry === null || entry.key !== key) return { result: { status: "loading" }, reload };
  if (entry.failed) return { result: { status: "error", notFound: entry.failed.notFound }, reload };
  const reloading = entry.stamp !== `${key}#${version}#${tick}`;
  return { result: { status: "ok", data: entry.data as T, reloading }, reload };
}
