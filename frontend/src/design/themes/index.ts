import { jua } from "./jua";
import { kitabu } from "./kitabu";
import { mahakama } from "./mahakama";
import { COLOR_ROLES, type Contrast, type Direction, type DirectionId, type Mode, type Palette } from "./types";

export const DIRECTIONS: Record<DirectionId, Direction> = { mahakama, jua, kitabu };
export const DIRECTION_IDS = Object.keys(DIRECTIONS) as DirectionId[];

/** The mode's palette with the more-contrast overrides applied when asked for. */
export function resolvePalette(direction: Direction, mode: Mode, contrast: Contrast): Palette {
  return contrast === "more" ? { ...direction.palettes[mode], ...direction.more[mode] } : direction.palettes[mode];
}

/** CSS custom properties (--hk-*) for one direction, mode and contrast. */
export function themeVariables(direction: Direction, mode: Mode, contrast: Contrast): Record<string, string> {
  const palette = resolvePalette(direction, mode, contrast);
  const vars: Record<string, string> = {
    "--hk-font-ui": direction.fonts.ui,
    "--hk-font-display": direction.fonts.display,
    "--hk-font-reading": direction.fonts.reading,
    "--hk-display-weight": direction.display.weight,
    "--hk-display-tracking": direction.display.tracking,
    "--hk-radius-sm": direction.radius.sm,
    "--hk-radius-md": direction.radius.md,
    "--hk-radius-lg": direction.radius.lg,
    "--hk-shadow-raised": direction.effects[mode].raised,
    "--hk-shadow-overlay": direction.effects[mode].overlay,
    "--hk-scrim": direction.effects[mode].scrim,
  };
  for (const role of COLOR_ROLES) vars[`--hk-${role}`] = palette[role];
  return vars;
}
