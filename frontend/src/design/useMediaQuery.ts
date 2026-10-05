import { useSyncExternalStore } from "react";

const supported = (): boolean => typeof window.matchMedia === "function";

/** Live result of a media query (false where matchMedia is unavailable, e.g. tests). */
export function useMediaQuery(query: string): boolean {
  const subscribe = (notify: () => void) => {
    if (!supported()) return () => {};
    const list = window.matchMedia(query);
    list.addEventListener("change", notify);
    return () => list.removeEventListener("change", notify);
  };
  return useSyncExternalStore(
    subscribe,
    () => supported() && window.matchMedia(query).matches,
    () => false,
  );
}
