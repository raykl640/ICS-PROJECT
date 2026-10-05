import type { Page } from "@playwright/test";

/** Waits for entry animations to finish, so an audit sees the settled page (looping animations are skipped). */
export async function settle(page: Page): Promise<void> {
  await page.evaluate(() =>
    Promise.all(
      document
        .getAnimations()
        .filter((a) => a.effect?.getComputedTiming().iterations !== Infinity)
        .map((a) => a.finished),
    ),
  );
}
