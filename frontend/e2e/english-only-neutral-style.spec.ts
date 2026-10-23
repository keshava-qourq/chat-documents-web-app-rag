import { expect, test } from "@playwright/test";

// US-018 / AC-060: the interface is English-only with light/neutral styling,
// and there is no language switcher anywhere in this release.

test.describe("AC-060: English-only, neutral styling, no language switcher", () => {
  test("declares English and shows English navigation labels on every screen", async ({ page }) => {
    await page.goto("/chat");

    const lang = await page.evaluate(() => document.documentElement.lang);
    expect(lang).toBe("en");

    const nav = page.getByLabel("Main navigation");
    await expect(nav.getByText("Chat", { exact: true })).toBeVisible();
    await expect(nav.getByText("Documents", { exact: true })).toBeVisible();

    // Documents screen renders its English copy, not placeholder/translated text.
    await nav.getByText("Documents", { exact: true }).click();
    await expect(page.getByRole("heading", { name: "Document library" })).toBeVisible();
    await expect(page.getByText("On the board")).toBeVisible();
  });

  test("has no language switcher control anywhere in the shell", async ({ page }) => {
    await page.goto("/chat");

    // No control advertises itself as a language switcher by accessible name.
    await expect(
      page.locator(
        '[aria-label*="language" i], [aria-label*="Language" i], [title*="language" i], select[name*="lang" i]',
      ),
    ).toHaveCount(0);

    // No common language-switcher labels (native-language autonyms for the
    // languages a switcher would typically offer) appear anywhere in the shell.
    for (const label of ["Español", "Français", "Deutsch", "Nederlands", "日本語"]) {
      await expect(page.getByText(label, { exact: true })).toHaveCount(0);
    }

    await page.getByLabel("Main navigation").getByText("Documents", { exact: true }).click();
    await expect(page.locator('[aria-label*="language" i], select[name*="lang" i]')).toHaveCount(0);
  });

  test("renders on a plain light background with no unstyled or dark theme applied", async ({
    page,
  }) => {
    await page.goto("/chat");

    const backgroundColor = await page.evaluate(
      () => getComputedStyle(document.body).backgroundColor,
    );
    // A neutral/light theme: not pure transparent/unset, and not a dark color.
    const match = backgroundColor.match(/\d+/g);
    expect(match).not.toBeNull();
    const [r, g, b] = match!.map(Number);
    const luminance = (r + g + b) / 3;
    expect(luminance).toBeGreaterThan(120);
  });
});
