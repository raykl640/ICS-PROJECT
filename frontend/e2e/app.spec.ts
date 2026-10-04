import { readFile } from "node:fs/promises";
import { expect, test } from "@playwright/test";

// Questions over the synthetic fake corpus (backend/tests/fake_pipeline.py).
const QUESTION = "My employer fired me and did not pay my wages. What are my rights?";
const NO_MATCH = "zzqv blorp quux";

test.use({ viewport: { width: 390, height: 844 } });

test("submit -> stream -> open sources -> download letter", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("textbox", { name: "Your question" }).fill(QUESTION);
  await page.getByRole("button", { name: "Ask" }).click();

  await expect(page.getByRole("status").filter({ hasText: "Answer complete." })).toBeVisible({ timeout: 15_000 });
  await page.getByRole("tab", { name: "Rights Explanation" }).click();
  await expect(page.getByRole("tabpanel")).toContainText("valid reason");

  await page.getByRole("button", { name: "Show the legal text used" }).click();
  const sources = page.locator("#sources-list li");
  await expect(sources.first()).toBeVisible();
  expect(await sources.count()).toBeGreaterThanOrEqual(2);

  await page.getByRole("tab", { name: "Formal Letter" }).click();
  await expect(page.getByRole("tabpanel")).toContainText("Dear [Recipient]");
  const [docx] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("link", { name: "Download letter (.docx)" }).click(),
  ]);
  expect(docx.suggestedFilename()).toBe("letter.docx");
  const bytes = await readFile((await docx.path())!);
  expect(bytes.subarray(0, 2).toString()).toBe("PK");

  const [txt] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("link", { name: "Download letter (.txt)" }).click(),
  ]);
  const letter = await readFile((await txt.path())!, "utf-8");
  expect(letter).toContain("Dear [Recipient]");
  expect(letter).toContain("legal information, not legal advice");

  await page.getByRole("button", { name: /Yes/ }).click();
  await page.getByRole("button", { name: "Send feedback" }).click();
  await expect(page.getByText(/Thank you/)).toBeVisible();
});

test("a question with no matching law shows the fallback screen", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("textbox", { name: "Your question" }).fill(NO_MATCH);
  await page.keyboard.press("Control+Enter");
  await expect(page.getByRole("heading", { name: "No matching provision found" })).toBeVisible();
  await expect(page.getByText(/cannot find a specific provision/)).toBeVisible();
  await expect(page.getByRole("tablist")).toHaveCount(0);
});
