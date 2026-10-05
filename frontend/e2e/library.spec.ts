import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const PASSWORD = "a long enough password";
const QUESTION = "My employer fired me and did not pay my wages. What are my rights?";

test("ask -> navigate away -> notified -> open from library -> follow-up -> edit letter -> export", async ({ page }) => {
  await page.goto("/signup");
  await page.getByRole("textbox", { name: "Username" }).fill(`lib${Date.now()}`);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByLabel("Repeat the password").fill(PASSWORD);
  await page.getByRole("button", { name: "Create account" }).click();
  await page.getByText("I have saved my recovery code").click();
  await page.getByRole("button", { name: "Continue" }).click();

  await page.goto("/");
  await page.getByRole("textbox", { name: /question/i }).first().fill(QUESTION);
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(page).toHaveURL(/\/ask\/[0-9a-f-]{36}$/);
  await expect(page.getByText("You can keep browsing")).toBeVisible();

  await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Library" }).click();
  await expect(page.getByText("Your answer is ready", { exact: true })).toBeVisible({ timeout: 15_000 });
  const { violations } = await new AxeBuilder({ page }).analyze();
  expect(violations.filter((v) => v.impact === "serious" || v.impact === "critical")).toEqual([]);

  await page.getByRole("link", { name: QUESTION }).click();
  await expect(page.getByRole("heading", { level: 1, name: QUESTION })).toBeVisible();
  await page.getByRole("textbox", { name: "Ask a follow-up question" }).fill("Can they also keep my last salary?");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(page.getByRole("article", { name: "Can they also keep my last salary?" })).toBeVisible({ timeout: 15_000 });

  const last = page.getByRole("article", { name: "Can they also keep my last salary?" });
  await last.getByRole("tab", { name: "Draft letter" }).click();
  await last.getByRole("button", { name: "Edit this letter" }).click();
  await expect(page).toHaveURL(/\/letters\//);
  const body = page.getByRole("textbox", { name: "Letter text" });
  await body.fill("[Date]\n\nDear Manager,\n\nPlease pay my wages.\n\nYours faithfully,\n[Your Name]");
  await page.getByRole("button", { name: "Save version" }).click();
  await expect(page.getByText("Saved as version 2")).toBeVisible();
  const download = page.waitForEvent("download");
  await page.getByRole("link", { name: /\.txt/ }).click();
  const file = await download;
  const text = await (await file.createReadStream())!.toArray();
  expect(Buffer.concat(text).toString()).toContain("Please pay my wages.");
  expect(Buffer.concat(text).toString()).toContain("not legal advice");
});
