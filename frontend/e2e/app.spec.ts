import { readFile } from "node:fs/promises";
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

// Questions over the synthetic fake corpus (backend/tests/fake_pipeline.py).
const QUESTION = "My employer fired me and did not pay my wages. What are my rights?";
const NO_MATCH = "zzqv blorp quux";

test.use({ viewport: { width: 390, height: 844 } });

// Any Content-Security-Policy violation (e.g. the pre-paint script's hash drifting) fails the test.
let cspViolations: string[] = [];
test.beforeEach(({ page }) => {
  cspViolations = [];
  page.on("console", (message) => {
    if (message.text().includes("Content Security Policy")) cspViolations.push(message.text());
  });
});
test.afterEach(() => expect(cspViolations).toEqual([]));

async function ask(page: Page, question: string) {
  await page.goto("/");
  await page.getByRole("textbox", { name: "Your question" }).fill(question);
  await page.getByRole("button", { name: "Ask" }).click();
  await expect(page).toHaveURL(/\/ask$/);
}

async function axe(page: Page) {
  const { violations } = await new AxeBuilder({ page }).analyze();
  return violations.filter((v) => v.impact === "serious" || v.impact === "critical").map((v) => `${v.id}: ${v.help}`);
}

test("ask -> stream -> sources -> download letter -> feedback", async ({ page }) => {
  await ask(page, QUESTION);
  await expect(page.getByRole("status").filter({ hasText: "Answer complete." })).toBeVisible({ timeout: 15_000 });
  await page.getByRole("tab", { name: "What the law says" }).click();
  await expect(page.getByRole("tabpanel")).toContainText("valid reason");

  await page.getByRole("button", { name: /^Sources \(\d+\)$/ }).click();
  const sheet = page.getByRole("dialog", { name: "Sources" });
  await expect(sheet.getByRole("listitem").first()).toBeVisible();
  expect(await sheet.getByRole("listitem").count()).toBeGreaterThanOrEqual(2);
  await page.keyboard.press("Escape");

  await page.getByRole("tab", { name: "Draft letter" }).click();
  await expect(page.getByRole("tabpanel")).toContainText("Dear [Recipient]");
  const [docx] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("link", { name: "Download letter (.docx)" }).click(),
  ]);
  expect(docx.suggestedFilename()).toBe("letter.docx");
  expect((await readFile((await docx.path())!)).subarray(0, 2).toString()).toBe("PK");
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
  await page.goto("/ask");
  await page.getByRole("textbox", { name: "Your question" }).fill(NO_MATCH);
  await page.keyboard.press("Control+Enter");
  await expect(page.getByRole("heading", { name: "No matching provision found" })).toBeVisible();
  await expect(page.getByText(/cannot find a specific provision/)).toBeVisible();
  await expect(page.getByRole("tablist")).toHaveCount(0);
});

test("a failed answer shows the error and Try again asks again", async ({ page }) => {
  let failNext = true;
  await page.route("**/api/stream/*", async (route) => {
    if (!failNext) return route.continue();
    failNext = false;
    await route.fulfill({
      status: 200,
      headers: { "content-type": "text/event-stream" },
      body: 'event: error\ndata: {"code": "llm_unavailable", "message": "Ollama is not reachable."}\n\n',
    });
  });
  await ask(page, QUESTION);
  await expect(page.getByRole("alert")).toContainText("The answer engine (Ollama) is not available.");
  await page.getByRole("button", { name: "Try again" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Answer complete." })).toBeVisible({ timeout: 15_000 });
});

test("deep links load and reload; unknown paths get the 404 page", async ({ page }) => {
  for (const [path, heading] of [
    ["/settings", "Settings"],
    ["/how-it-works", "How HakiAI works"],
    ["/ask", "Ask a question"],
  ]) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1, name: heading })).toBeVisible();
    await page.reload();
    await expect(page.getByRole("heading", { level: 1, name: heading })).toBeVisible();
  }
  await page.goto("/no/such/page");
  await expect(page.getByRole("heading", { level: 1, name: "Page not found" })).toBeVisible();
});

test("saved settings are applied by the pre-paint script, before and without the app's JavaScript", async ({
  page,
}) => {
  await page.goto("/settings");
  await page.getByRole("radio", { name: "Dark" }).click();
  await page.getByRole("radio", { name: "Extra large" }).click();
  await page.route("**/assets/*.js", (route) => route.abort());
  await page.reload();
  const attrs = await page.evaluate(() => ({ ...document.documentElement.dataset }));
  expect(attrs).toMatchObject({ theme: "dark", text: "xl" });
  const background = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
  expect(background).toBe("rgb(14, 23, 18)");
});

for (const scheme of ["light", "dark"] as const) {
  test(`axe: Home, Ask (answered) and Settings have no serious or critical issues (${scheme})`, async ({ page }) => {
    await page.emulateMedia({ colorScheme: scheme });
    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    expect(await axe(page)).toEqual([]);

    await page.getByRole("textbox", { name: "Your question" }).fill(QUESTION);
    await page.getByRole("button", { name: "Ask" }).click();
    await expect(page.getByRole("status").filter({ hasText: "Answer complete." })).toBeVisible({ timeout: 15_000 });
    expect(await axe(page)).toEqual([]);

    await page.goto("/settings");
    await expect(page.getByRole("heading", { level: 1, name: "Settings" })).toBeVisible();
    expect(await axe(page)).toEqual([]);
  });
}
