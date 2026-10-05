import { COLOR_ROLES, contrastRatio, MIN_RATIO, PAIRS, type Contrast, type Mode } from "./contrast";
import tokensCss from "./tokens.css?raw";

// The blocks of tokens.css by selector, in source order.
const BLOCKS = [...tokensCss.matchAll(/([^{}]+)\{([^}]*)\}/g)].map(([, selector, body]) => ({
  selector: selector.replace(/\/\*[\s\S]*?\*\//g, "").trim(),
  vars: Object.fromEntries(
    [...body.matchAll(/--hk-([\w-]+):\s*([^;]+);/g)].map(([, name, value]) => [name, value.trim()]),
  ),
}));

/** Token values for one state, applying the blocks whose attribute selectors match, by specificity then order. */
function resolve(mode: Mode, contrast: Contrast): Record<string, string> {
  const attrs: Record<string, string> = { theme: mode, contrast };
  const matching = BLOCKS.filter(({ selector }) =>
    [...selector.matchAll(/\[data-(\w+)="(\w+)"\]/g)].every(([, name, value]) => attrs[name] === value),
  );
  const specificity = (selector: string) => selector.split("[").length;
  return Object.assign(
    {},
    ...matching.sort((a, b) => specificity(a.selector) - specificity(b.selector)).map((b) => b.vars),
  );
}

describe("WCAG contrast of tokens.css", () => {
  it("known reference ratios and the four expected blocks", () => {
    expect(contrastRatio("#000000", "#ffffff")).toBeCloseTo(21, 5);
    expect(contrastRatio("#777777", "#ffffff")).toBeCloseTo(4.48, 2);
    expect(() => contrastRatio("#fff", "#000000")).toThrow();
    expect(BLOCKS.map((b) => b.selector)).toEqual([
      ":root",
      ':root[data-theme="dark"]',
      ':root[data-contrast="more"]',
      ':root[data-theme="dark"][data-contrast="more"]',
    ]);
  });

  it("dark + more overrides every key the light more-contrast block sets", () => {
    expect(Object.keys(BLOCKS[3].vars).sort()).toEqual(Object.keys(BLOCKS[2].vars).sort());
  });

  for (const mode of ["light", "dark"] as const) {
    for (const contrast of ["standard", "more"] as const) {
      it(`${mode} ${contrast}: every declared pair meets its minimum`, () => {
        const palette = resolve(mode, contrast);
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
});
