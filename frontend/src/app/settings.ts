// Local-only appearance and language settings (localStorage). index.html's pre-paint script applies the same rules
// before the first paint; settings.test.ts runs that script against htmlAttributes() to keep the two in step.
import type { UiLanguage } from "../api/types";
import type { Contrast, Mode } from "../design/contrast";

export type ThemeChoice = "system" | Mode;
export type ContrastChoice = "system" | Contrast;
export type TextSize = "sm" | "md" | "lg" | "xl";
export type MotionChoice = "system" | "reduce";

export interface Settings {
  theme: ThemeChoice;
  contrast: ContrastChoice;
  text: TextSize;
  motion: MotionChoice;
  language: UiLanguage;
}

export const SETTINGS_KEY = "hakiai.settings";
export const TEXT_SIZES: TextSize[] = ["sm", "md", "lg", "xl"];

export const DEFAULT_SETTINGS: Settings = {
  theme: "system",
  contrast: "system",
  text: "md",
  motion: "system",
  language: "en",
};

const oneOf = <T extends string>(value: unknown, allowed: readonly T[], fallback: T): T =>
  allowed.includes(value as T) ? (value as T) : fallback;

function readStored(): Partial<Record<keyof Settings, unknown>> {
  try {
    return JSON.parse(localStorage.getItem(SETTINGS_KEY) ?? "{}") ?? {};
  } catch {
    return {};
  }
}

/** Stored settings, each field validated; defaults where storage is empty, unreadable or blocked. */
export function loadSettings(): Settings {
  const raw = readStored();
  return {
    theme: oneOf(raw.theme, ["system", "light", "dark"], DEFAULT_SETTINGS.theme),
    contrast: oneOf(raw.contrast, ["system", "standard", "more"], DEFAULT_SETTINGS.contrast),
    text: oneOf(raw.text, TEXT_SIZES, DEFAULT_SETTINGS.text),
    motion: oneOf(raw.motion, ["system", "reduce"], DEFAULT_SETTINGS.motion),
    language: oneOf(raw.language, ["en", "sw"], DEFAULT_SETTINGS.language),
  };
}

/** Persist settings; silently does nothing where storage is blocked (private windows). */
export function saveSettings(settings: Settings): void {
  try {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
  } catch {
    // Settings then last for this page view only.
  }
}

export interface HtmlAttributes {
  theme: Mode;
  contrast: Contrast;
  text: TextSize;
  motion: MotionChoice;
  lang: UiLanguage;
}

/** The <html> attributes for settings, resolving "system" from the OS preferences. */
export function htmlAttributes(settings: Settings, systemDark: boolean, systemMore: boolean): HtmlAttributes {
  return {
    theme: settings.theme === "system" ? (systemDark ? "dark" : "light") : settings.theme,
    contrast: settings.contrast === "system" ? (systemMore ? "more" : "standard") : settings.contrast,
    text: settings.text,
    motion: settings.motion,
    lang: settings.language,
  };
}

/** Write the attributes onto the root element. */
export function applyAttributes(root: HTMLElement, attrs: HtmlAttributes): void {
  root.dataset.theme = attrs.theme;
  root.dataset.contrast = attrs.contrast;
  root.dataset.text = attrs.text;
  root.dataset.motion = attrs.motion;
  root.lang = attrs.lang;
}

/** True when motion should be avoided (in-app setting or OS preference). */
export const reduceMotion = (): boolean =>
  document.documentElement.dataset.motion === "reduce" ||
  (typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
