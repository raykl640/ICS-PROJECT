import { useLayoutEffect, useSyncExternalStore } from "react";
import { DIRECTIONS, themeVariables } from "./themes";
import type { Contrast, DirectionId, Mode, TextSize } from "./themes/types";

export interface ThemeSettings {
  direction: DirectionId;
  mode: Mode | "system";
  contrast: Contrast | "system";
  text: TextSize;
  motion: "system" | "reduce";
}

const noop = () => () => {};

/** Live result of a media query (false where matchMedia is unavailable, e.g. tests). */
export function useMediaQuery(query: string): boolean {
  const subscribe = (notify: () => void) => {
    if (typeof window.matchMedia !== "function") return noop();
    const list = window.matchMedia(query);
    list.addEventListener("change", notify);
    return () => list.removeEventListener("change", notify);
  };
  const read = () => typeof window.matchMedia === "function" && window.matchMedia(query).matches;
  return useSyncExternalStore(typeof window.matchMedia === "function" ? subscribe : noop, read, () => false);
}

/** Write the resolved tokens and data-* attributes onto an element (the document root in the app). */
export function applyTheme(root: HTMLElement, settings: ThemeSettings, mode: Mode, contrast: Contrast): void {
  for (const [name, value] of Object.entries(themeVariables(DIRECTIONS[settings.direction], mode, contrast))) {
    root.style.setProperty(name, value);
  }
  root.style.colorScheme = mode;
  Object.assign(root.dataset, {
    direction: settings.direction,
    theme: mode,
    contrast,
    text: settings.text,
    motion: settings.motion,
  });
}

/** Resolve "system" choices from the OS and keep the root element's tokens in sync. */
export function useApplyTheme(settings: ThemeSettings, root: HTMLElement = document.documentElement): void {
  const systemDark = useMediaQuery("(prefers-color-scheme: dark)");
  const systemMore = useMediaQuery("(prefers-contrast: more)");
  const mode: Mode = settings.mode === "system" ? (systemDark ? "dark" : "light") : settings.mode;
  const contrast: Contrast = settings.contrast === "system" ? (systemMore ? "more" : "standard") : settings.contrast;
  useLayoutEffect(() => applyTheme(root, settings, mode, contrast), [root, settings, mode, contrast]);
}
