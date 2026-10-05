import indexHtml from "../../index.html?raw";
import { htmlAttributes, loadSettings, SETTINGS_KEY } from "./settings";

const PREPAINT = /<script>([\s\S]*?)<\/script>/.exec(indexHtml)![1];

/** matchMedia answering the two OS preferences the pre-paint script reads. */
function stubMedia(dark: boolean, more: boolean) {
  vi.stubGlobal("matchMedia", (query: string) => ({
    matches: (query.includes("color-scheme: dark") && dark) || (query.includes("contrast: more") && more),
  }));
}

afterEach(() => vi.unstubAllGlobals());

const STORED = [
  null,
  "not json",
  "null",
  "42",
  JSON.stringify({ theme: "dark", contrast: "more", text: "xl", motion: "reduce", language: "sw" }),
  JSON.stringify({ theme: "light", contrast: "standard", text: "sm" }),
  JSON.stringify({ theme: "purple", contrast: 3, text: "huge", motion: "fast", language: "fr" }),
];

test("stored settings are validated field by field", () => {
  localStorage.setItem(SETTINGS_KEY, JSON.stringify({ theme: "dark", text: "huge", language: "sw" }));
  expect(loadSettings()).toEqual({ theme: "dark", contrast: "system", text: "md", motion: "system", language: "sw" });
  localStorage.setItem(SETTINGS_KEY, "{broken");
  expect(loadSettings().theme).toBe("system");
});

test.each(
  STORED.flatMap((stored) =>
    [false, true].flatMap((dark) => [false, true].map((more) => [stored, dark, more] as const)),
  ),
)("pre-paint script matches settings.ts for stored %s (dark OS %s, more-contrast OS %s)", (stored, dark, more) => {
  if (stored !== null) localStorage.setItem(SETTINGS_KEY, stored);
  stubMedia(dark, more);
  new Function(PREPAINT)();
  const root = document.documentElement;
  const expected = htmlAttributes(loadSettings(), dark, more);
  expect({ ...root.dataset, lang: root.lang }).toMatchObject({
    theme: expected.theme,
    contrast: expected.contrast,
    text: expected.text,
    motion: expected.motion,
    lang: expected.lang,
  });
});
