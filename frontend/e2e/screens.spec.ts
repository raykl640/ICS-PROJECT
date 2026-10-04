import { expect, test } from "@playwright/test";

// @screens: screenshots for visual review (npm run screenshots); written to SCREENSHOT_DIR or test-results/screens.
const DIR = process.env.SCREENSHOT_DIR ?? "test-results/screens";
const QUESTION = "My employer fired me and did not pay my wages. What are my rights?";

for (const [name, width, height] of [
  ["mobile", 375, 812],
  ["desktop", 1280, 860],
] as const) {
  for (const scheme of ["light", "dark"] as const) {
    test(`@screens ${name} ${scheme}`, async ({ page }) => {
      await page.emulateMedia({ colorScheme: scheme });
      await page.setViewportSize({ width, height });
      await page.goto("/");
      await page.screenshot({ path: `${DIR}/${name}-${scheme}-landing.png`, fullPage: true });

      await page.getByRole("textbox", { name: "Your question" }).fill(QUESTION);
      await page.getByRole("button", { name: "Ask" }).click();
      await page.waitForTimeout(250);
      await page.screenshot({ path: `${DIR}/${name}-${scheme}-streaming.png`, fullPage: true });
      await expect(page.getByRole("status").filter({ hasText: "Answer complete." })).toBeVisible({ timeout: 15_000 });
      await page.getByRole("tab", { name: "Rights Explanation" }).click();
      const cite = page.locator("button.cite").first();
      if (await cite.count()) await cite.click();
      await page.waitForTimeout(600);
      await page.screenshot({ path: `${DIR}/${name}-${scheme}-answer.png`, fullPage: true });
      await page.screenshot({ path: `${DIR}/${name}-${scheme}-answer-viewport.png` });
      await page.getByRole("tab", { name: "Formal Letter" }).click();
      await page.screenshot({ path: `${DIR}/${name}-${scheme}-letter.png`, fullPage: true });

      await page.getByRole("button", { name: "Ask another question" }).last().click();
      await page.getByRole("textbox", { name: "Your question" }).fill("zzqv blorp quux");
      await page.getByRole("button", { name: "Ask" }).click();
      await expect(page.getByRole("heading", { name: "No matching provision found" })).toBeVisible();
      await page.screenshot({ path: `${DIR}/${name}-${scheme}-null.png`, fullPage: true });
    });
  }
}
