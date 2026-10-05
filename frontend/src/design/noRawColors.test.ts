// Components and mock screens may only use colour tokens; raw values live in src/design/themes/ alone.
const SOURCES = import.meta.glob<string>(["./components/**/*.{ts,tsx}", "./styleguide/**/*.{ts,tsx}", "./*.css"], {
  query: "?raw",
  import: "default",
  eager: true,
});
const RAW_COLOR = /#(?:[0-9a-f]{8}|[0-9a-f]{6}|[0-9a-f]{3,4})\b|\b(?:rgba?|hsla?|oklch|oklab)\(/gi;

describe("no raw colours outside the theme files", () => {
  it("finds the component files and detects raw values", () => {
    expect(Object.keys(SOURCES).length).toBeGreaterThan(10);
    for (const raw of ["bg-[#fff]", "color: #12ab34", "rgb(0 0 0 / 0.5)", "oklch(0.5 0.1 120)"]) {
      expect(raw.match(RAW_COLOR), raw).not.toBeNull();
    }
    expect('href="#source-1" #section'.match(RAW_COLOR)).toBeNull();
  });

  it.each(Object.entries(SOURCES))("%s", (_file, source) => {
    expect(source.match(RAW_COLOR) ?? []).toEqual([]);
  });
});
