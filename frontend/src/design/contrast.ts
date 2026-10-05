import type { ColorRole, Contrast } from "./themes/types";

const channel = (value: number): number => {
  const c = value / 255;
  return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
};

/** WCAG 2.x relative luminance of a #rrggbb colour. */
export function luminance(hex: string): number {
  if (!/^#[0-9a-f]{6}$/i.test(hex)) throw new Error(`Not a #rrggbb colour: ${hex}`);
  const [r, g, b] = [1, 3, 5].map((i) => channel(parseInt(hex.slice(i, i + 2), 16)));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

/** WCAG contrast ratio between two #rrggbb colours (1–21). */
export function contrastRatio(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

/** reading: statute and answer text; body: other text; ui: borders, focus rings, non-text marks. */
export type PairKind = "reading" | "body" | "ui";

export const MIN_RATIO: Record<Contrast, Record<PairKind, number>> = {
  standard: { reading: 7, body: 4.5, ui: 3 },
  more: { reading: 10, body: 7, ui: 4.5 },
};

const BACKGROUNDS: ColorRole[] = ["canvas", "surface", "raised"];
const on = (fg: ColorRole, kind: PairKind, bgs: ColorRole[] = BACKGROUNDS) => bgs.map((bg) => ({ fg, bg, kind }));

/** Every foreground/background pair the components use. line-subtle is decorative only and never a boundary. */
export const PAIRS: { fg: ColorRole; bg: ColorRole; kind: PairKind }[] = [
  ...on("ink", "reading", [...BACKGROUNDS, "highlight"]),
  ...on("ink", "body", ["sunken"]),
  ...on("ink-muted", "body", [...BACKGROUNDS, "sunken"]),
  ...on("brand", "body", [...BACKGROUNDS, "sunken"]),
  ...on("brand-ink", "body", ["brand"]),
  ...on("accent", "body"),
  ...on("success", "body"),
  ...on("warn", "body"),
  ...on("danger", "body"),
  ...on("info", "body"),
  ...on("line", "ui", [...BACKGROUNDS, "sunken"]),
  // The focus ring has a 2px offset, so it always sits on a background, never on a filled control.
  ...on("focus", "ui", [...BACKGROUNDS, "sunken"]),
];
