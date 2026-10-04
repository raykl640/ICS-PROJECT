/** True if the media query matches (false where matchMedia is unavailable, e.g. tests). */
export const matches = (query: string): boolean =>
  typeof window.matchMedia === "function" && window.matchMedia(query).matches;

export const prefersReducedMotion = (): boolean => matches("(prefers-reduced-motion: reduce)");
export const isWideScreen = (): boolean => matches("(min-width: 1024px)");
