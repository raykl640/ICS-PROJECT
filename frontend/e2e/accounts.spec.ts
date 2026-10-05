import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const PASSWORD = "a long enough password";

test("sign up -> recovery code -> sign out -> sign in -> lock -> unlock", async ({ page }) => {
  const username = `e2e${Date.now()}`;
  await page.goto("/welcome");
  await page.getByRole("link", { name: "Create an account" }).click();
  await page.getByRole("textbox", { name: "Username" }).fill(username);
  await page.getByLabel("Your name (shown in HakiAI)").fill("Test User");
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByLabel("Repeat the password").fill(PASSWORD);
  const { violations } = await new AxeBuilder({ page }).analyze();
  expect(violations.filter((v) => v.impact === "serious" || v.impact === "critical")).toEqual([]);
  await page.getByRole("button", { name: "Create account" }).click();

  await expect(page.getByRole("heading", { name: "Save your recovery code" })).toBeVisible();
  await expect(page.getByTestId("recovery-code")).toHaveText(/^[A-Z2-7]{4}(-[A-Z2-7]{4}){4}$/);
  await expect(page.getByRole("button", { name: "Continue" })).toBeDisabled();
  await page.getByText("I have saved my recovery code").click();
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page.getByText("Guest: nothing is saved.")).toHaveCount(0);

  await page.getByRole("button", { name: "Account", exact: true }).click();
  await page.getByRole("menuitem", { name: "Sign out" }).click();
  await expect(page.getByText("Guest: nothing is saved.")).toBeVisible();

  await page.goto("/signin");
  await page.getByRole("textbox", { name: "Username" }).fill(username);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { level: 1, name: /Know where you stand/ })).toBeVisible();

  await page.getByRole("button", { name: "Account", exact: true }).click();
  await page.getByRole("menuitem", { name: "Lock" }).click();
  await expect(page.getByRole("heading", { name: "HakiAI is locked" })).toBeVisible();
  await page.reload(); // still locked after a reload: the key only lives in server memory
  await expect(page.getByRole("heading", { name: "HakiAI is locked" })).toBeVisible();
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Unlock" }).click();
  await expect(page.getByRole("navigation", { name: "Main" })).toBeVisible();

  await page.goto("/settings?tab=profile");
  await page.getByRole("textbox", { name: "Full name" }).fill("Test User Kamau");
  await page.getByRole("button", { name: "Save profile" }).click();
  await expect(page.getByText("Saved.")).toBeVisible();
});
