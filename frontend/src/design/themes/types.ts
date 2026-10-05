// Design tokens shared by every direction. Colours are #rrggbb only (the contrast test parses them).

export const COLOR_ROLES = [
  "canvas",
  "surface",
  "raised",
  "sunken",
  "ink",
  "ink-muted",
  "line",
  "line-subtle",
  "brand",
  "brand-ink",
  "accent",
  "success",
  "warn",
  "danger",
  "info",
  "focus",
  "highlight",
] as const;

export type ColorRole = (typeof COLOR_ROLES)[number];
export type Palette = Record<ColorRole, string>;

export type DirectionId = "mahakama" | "jua" | "kitabu";
export type Mode = "light" | "dark";
export type Contrast = "standard" | "more";
export type TextSize = "sm" | "md" | "lg" | "xl";

/** Non-colour effects: elevation shadows and the scrim behind dialogs. */
export interface Effects {
  raised: string;
  overlay: string;
  scrim: string;
}

export interface Direction {
  id: DirectionId;
  name: string;
  /** One line on the intended feel (style guide only). */
  summary: string;
  fonts: { ui: string; display: string; reading: string };
  /** Display headings: weight and letter spacing. */
  display: { weight: string; tracking: string };
  radius: { sm: string; md: string; lg: string };
  palettes: Record<Mode, Palette>;
  /** More-contrast overrides applied on top of the mode's palette. */
  more: Record<Mode, Partial<Palette>>;
  effects: Record<Mode, Effects>;
}
