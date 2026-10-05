import AxeBuilder from "@axe-core/playwright";
import { settle } from "./settle";
import { expect, test, type Page } from "@playwright/test";

const PASSWORD = "a long enough password";

async function expectNoSeriousAxe(page: Page) {
  await settle(page);
  const { violations } = await new AxeBuilder({ page }).analyze();
  expect(violations.filter((v) => v.impact === "serious" || v.impact === "critical")).toEqual([]);
}

test("browse Act -> section -> follow ref -> bookmark -> find it in Library", async ({ page }) => {
  await page.goto("/signup");
  await page.getByRole("textbox", { name: "Username" }).fill(`laws${Date.now()}`);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByLabel("Repeat the password").fill(PASSWORD);
  await page.getByRole("button", { name: "Create account" }).click();
  await page.getByText("I have saved my recovery code").click();
  await page.getByRole("button", { name: "Continue" }).click();

  await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Laws" }).click();
  await page.getByRole("link", { name: /Sample Employment Act/ }).click();
  await page
    .getByRole("navigation", { name: "Contents" })
    .getByRole("link", { name: /Summary dismissal/ })
    .click();
  await expect(page.getByRole("heading", { level: 1, name: "Section 8 — Summary dismissal" })).toBeVisible();
  await expectNoSeriousAxe(page);

  await page.getByRole("region", { name: "This section refers to" }).getByRole("link", { name: "Section 4" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Section 4 — Unfair termination" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Cited by" })).toContainText("section 8");
  await page.getByRole("button", { name: "Save section" }).click();
  await expect(page.getByRole("button", { name: "Section saved" })).toBeDisabled();

  await page.goto("/library?tab=saved");
  await expect(page.getByText("Sample Employment Act — s. 4: Unfair termination")).toBeVisible();
  await page.goto("/laws");
  await expect(page.getByRole("link", { name: /Sample Employment Act — 4: Unfair termination/ })).toBeVisible();
});

test("search -> open hit -> Ask about this", async ({ page }) => {
  await page.goto("/laws");
  await page
    .getByRole("searchbox", { name: "Search the laws" })
    .or(page.getByLabel("Search the laws"))
    .fill("evict tenant");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page).toHaveURL(/\/search\?q=evict\+tenant/);
  const hit = page.getByRole("link", { name: "Sample Tenancy Act, Section 3: Eviction" });
  await expect(hit).toBeVisible();
  await expect(page.locator("mark").first()).toBeVisible();
  await expectNoSeriousAxe(page);

  await hit.click();
  await expect(page.getByRole("heading", { level: 1, name: "Section 3 — Eviction" })).toBeVisible();
  await page.getByRole("button", { name: "Ask about this section" }).click();
  await expect(page.getByRole("textbox", { name: /question/i }).first()).toHaveValue(
    "Sample Tenancy Act, section 3 (Eviction): ",
  );
});
