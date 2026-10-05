import { expect, test, type Page } from "@playwright/test";

// Screenshots of the three mock screens per direction, width and mode → docs/design/<direction>/<screen>-<width>-<mode>.png.
const OUT = process.env.DESIGN_DIR ?? "../docs/design";
const DIRECTIONS = ["mahakama", "jua", "kitabu"] as const;
const SCREENS = ["home", "conversation", "reader"] as const;
const WIDTHS = [
  [1280, 860],
  [375, 812],
] as const;
const MODES = ["light", "dark"] as const;

async function open(page: Page, query: Record<string, string>) {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto(`/styleguide?${new URLSearchParams({ bare: "1", ...query })}`);
  await page.evaluate(() => document.fonts.ready);
}

/** Full-page shot with the viewport grown to the page, so sticky bars sit where a reader would meet them. */
async function shoot(page: Page, width: number, height: number, path: string) {
  const full = await page.evaluate(() => document.documentElement.scrollHeight);
  await page.setViewportSize({ width, height: Math.max(height, full) });
  await page.screenshot({ path });
  await page.setViewportSize({ width, height });
}

for (const direction of DIRECTIONS) {
  test(`${direction} screens`, async ({ page }) => {
    for (const [width, height] of WIDTHS) {
      await page.setViewportSize({ width, height });
      for (const mode of MODES) {
        for (const view of SCREENS) {
          await open(page, { direction, theme: mode, view });
          await expect(page.getByRole("navigation", { name: "Main" })).toBeVisible();
          await shoot(page, width, height, `${OUT}/${direction}/${view}-${width}-${mode}.png`);
        }
      }
    }
    // Narrow screens show sources as a bottom sheet: one extra shot with it open.
    await page.setViewportSize({ width: 375, height: 812 });
    await open(page, { direction, theme: "light", view: "conversation", sources: "1" });
    await expect(page.getByRole("dialog", { name: "Sources" })).toBeVisible();
    await page.screenshot({ path: `${OUT}/${direction}/conversation-375-light-sources.png` });
  });
}
