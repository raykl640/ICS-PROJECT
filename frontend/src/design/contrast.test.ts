import { contrastRatio, MIN_RATIO, PAIRS } from "./contrast";
import { DIRECTION_IDS, DIRECTIONS, resolvePalette } from "./themes";
import { COLOR_ROLES, type Contrast, type Mode } from "./themes/types";

const MODES: Mode[] = ["light", "dark"];
const CONTRASTS: Contrast[] = ["standard", "more"];

describe("WCAG contrast", () => {
  it("known reference ratios", () => {
    expect(contrastRatio("#000000", "#ffffff")).toBeCloseTo(21, 5);
    expect(contrastRatio("#777777", "#ffffff")).toBeCloseTo(4.48, 2);
    expect(() => contrastRatio("#fff", "#000000")).toThrow();
  });

  for (const id of DIRECTION_IDS) {
    for (const mode of MODES) {
      for (const contrast of CONTRASTS) {
        it(`${id} ${mode} ${contrast}: every declared pair meets its minimum`, () => {
          const palette = resolvePalette(DIRECTIONS[id], mode, contrast);
          for (const role of COLOR_ROLES) expect(palette[role], role).toMatch(/^#[0-9a-f]{6}$/);
          const failures = PAIRS.map(({ fg, bg, kind }) => ({
            pair: `${fg} on ${bg} (${kind})`,
            ratio: contrastRatio(palette[fg], palette[bg]),
            min: MIN_RATIO[contrast][kind],
          }))
            .filter(({ ratio, min }) => ratio < min)
            .map(({ pair, ratio, min }) => `${pair}: ${ratio.toFixed(2)} < ${min}`);
          expect(failures).toEqual([]);
        });
      }
    }
  }
});
