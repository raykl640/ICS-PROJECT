import { expect, test, type Page } from "@playwright/test";

// @screens: screenshots for visual review (npm run screenshots); written to SCREENSHOT_DIR or test-results/screens.
const DIR = process.env.SCREENSHOT_DIR ?? "test-results/screens";
const QUESTION = "My employer fired me and did not pay my wages. What are my rights?";

/** Full-page shot with the viewport grown to the page, so sticky bars sit where a reader meets them. */
async function shoot(page: Page, name: string) {
  const { width, height } = page.viewportSize()!;
  const full = await page.evaluate(() => document.documentElement.scrollHeight);
  await page.setViewportSize({ width, height: Math.max(height, full) });
  await page.screenshot({ path: `${DIR}/${name}.png` });
  await page.setViewportSize({ width, height });
}

for (const [name, width, height] of [
  ["375", 375, 812],
  ["1280", 1280, 860],
] as const) {
  for (const scheme of ["light", "dark"] as const) {
    test(`@screens ${name} ${scheme}`, async ({ page }) => {
      const tag = `${name}-${scheme}`;
      await page.emulateMedia({ colorScheme: scheme, reducedMotion: "reduce" });
      await page.setViewportSize({ width, height });
      await page.goto("/");
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      await page.evaluate(() => document.fonts.ready);
      await shoot(page, `${tag}-home`);

      await page.getByRole("textbox", { name: "Your question" }).fill(QUESTION);
      await page.getByRole("button", { name: "Ask" }).click();
      await page.waitForTimeout(300);
      await shoot(page, `${tag}-streaming`);
      await expect(page.getByRole("status").filter({ hasText: "Answer complete." })).toBeVisible({ timeout: 15_000 });
      await page.getByRole("tab", { name: "What the law says" }).click();
      const cite = page.locator("button.cite").first();
      if (await cite.count()) await cite.click();
      await page.waitForTimeout(300);
      await page.screenshot({ path: `${DIR}/${tag}-answer-viewport.png` });
      if (width < 1024) await page.keyboard.press("Escape");
      await shoot(page, `${tag}-answer`);
      await page.getByRole("tab", { name: "Draft letter" }).click();
      await shoot(page, `${tag}-letter`);

      await page.getByRole("textbox", { name: "Ask another question" }).fill("zzqv blorp quux");
      await page.getByRole("button", { name: "Ask" }).click();
      await expect(page.getByRole("heading", { name: "No matching provision found" })).toBeVisible();
      await shoot(page, `${tag}-null`);

      for (const path of ["laws", "settings", "how-it-works", "nope", "welcome", "signin", "signup"]) {
        await page.goto(`/${path}`);
        await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
        await shoot(page, `${tag}-${path}`);
      }

      await page.goto("/laws");
      await page.getByRole("link", { name: /Sample Employment Act/ }).click();
      await expect(page.getByRole("heading", { level: 1, name: "Sample Employment Act" })).toBeVisible();
      await shoot(page, `${tag}-law-act`);
      await page
        .getByRole("link", { name: /Unfair termination/ })
        .first()
        .click();
      await expect(page.getByRole("heading", { level: 1, name: /Unfair termination/ })).toBeVisible();
      await shoot(page, `${tag}-law-section`);
      await page.goto("/signup");

      // Signed-in screens: recovery code, Profile and Privacy, lock screen.
      const password = "a long enough password";
      await page.getByRole("textbox", { name: "Username" }).fill(`shots${tag.replace(/\W/g, "")}${Date.now()}`);
      await page.getByLabel("Password", { exact: true }).fill(password);
      await page.getByLabel("Repeat the password").fill(password);
      await page.getByRole("button", { name: "Create account" }).click();
      await expect(page.getByRole("heading", { name: "Save your recovery code" })).toBeVisible();
      await shoot(page, `${tag}-recovery`);
      await page.getByText("I have saved my recovery code").click();
      await page.getByRole("button", { name: "Continue" }).click();
      await page.goto("/library");
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      await shoot(page, `${tag}-library`);
      for (const tab of ["profile", "privacy"]) {
        await page.goto(`/settings?tab=${tab}`);
        await expect(
          page.getByRole("tab", { name: tab === "profile" ? "Profile" : "Privacy", selected: true }),
        ).toBeVisible();
        await shoot(page, `${tag}-settings-${tab}`);
      }
      await page.getByRole("button", { name: "Account", exact: true }).click();
      await page.getByRole("menuitem", { name: "Lock" }).click();
      await expect(page.getByRole("heading", { name: "HakiAI is locked" })).toBeVisible();
      await shoot(page, `${tag}-locked`);
    });
  }
}
