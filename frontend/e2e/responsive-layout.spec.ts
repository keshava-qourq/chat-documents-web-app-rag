import { expect, test } from "@playwright/test";

// US-018: Navigate a responsive two-area layout.

test.describe("AC-058: desktop layout keeps the sidebar alongside the open area", () => {
  test.use({ viewport: { width: 1280, height: 800 } });

  test("sidebar and chat are visible together, and switching to documents preserves the in-progress thread", async ({
    page,
  }) => {
    await page.goto("/");
    await expect(page).toHaveURL(/\/chat$/);

    // The sidebar is visible alongside the chat area -- no hamburger needed at
    // this width.
    const nav = page.getByLabel("Main navigation");
    await expect(nav).toBeVisible();
    await expect(page.getByLabel("Open navigation menu")).toBeHidden();

    const chatPanel = page.getByTestId("chat-panel");
    await expect(chatPanel).toBeVisible();
    await expect(nav).toBeVisible();

    // Put something unsaved into the open thread's composer so a lost place
    // would be observable.
    const composer = chatPanel.getByRole("textbox").first();
    const draft = "Does the Berlin office close for the Christmas holidays?";
    await composer.fill(draft);
    await expect(composer).toHaveValue(draft);

    // Switch to Documents without losing the open thread's draft.
    await nav.getByText("Documents", { exact: true }).click();
    await expect(page.getByTestId("documents-panel")).toBeVisible();
    await expect(chatPanel).toBeHidden();

    // Switch back: the chat panel was never torn down, so the draft is still there.
    await nav.getByText("Chat", { exact: true }).click();
    await expect(chatPanel).toBeVisible();
    await expect(composer).toHaveValue(draft);
  });
});

test.describe("AC-059: narrow mobile layout reaches every area without horizontal scroll", () => {
  test.use({ viewport: { width: 375, height: 700 } });

  test("sidebar, chat and documents are each reachable via the mobile drawer with no horizontal overflow", async ({
    page,
  }) => {
    await page.goto("/chat");

    // No horizontal scrollbar at this width.
    const hasHorizontalOverflow = await page.evaluate(
      () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
    );
    expect(hasHorizontalOverflow).toBe(false);

    // Desktop sidebar is not shown; the hamburger is the way in instead.
    const toggle = page.getByLabel("Open navigation menu");
    await expect(toggle).toBeVisible();
    await expect(page.getByTestId("chat-panel")).toBeVisible();

    // Open the drawer: the nav (and therefore every area) is reachable.
    await toggle.click();
    const drawerNav = page.getByLabel("Main navigation");
    await expect(drawerNav).toBeVisible();
    await expect(page.getByLabel("Close navigation menu")).toBeVisible();

    // Jump to Documents.
    await drawerNav.getByText("Documents", { exact: true }).click();
    await expect(page.getByTestId("documents-panel")).toBeVisible();
    const overflowOnDocuments = await page.evaluate(
      () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
    );
    expect(overflowOnDocuments).toBe(false);

    // Drawer closed itself on navigation; open it again to reach Setup.
    await page.getByLabel("Open navigation menu").click();
    await page.getByLabel("Main navigation").getByText("Setup & status", { exact: true }).click();
    await expect(page.getByTestId("setup-panel")).toBeVisible();

    // Back to chat, confirming it is still reachable too.
    await page.getByLabel("Open navigation menu").click();
    await page.getByLabel("Main navigation").getByText("Chat", { exact: true }).click();
    await expect(page.getByTestId("chat-panel")).toBeVisible();
  });

  test("the drawer scrim closes the drawer without navigating away", async ({ page }) => {
    await page.goto("/chat");
    await page.getByLabel("Open navigation menu").click();
    // Click well to the right of the 256px-wide (max 80vw) drawer so the hit
    // lands on the scrim behind it, not on the drawer itself.
    await page.getByTestId("nav-drawer-scrim").click({ position: { x: 350, y: 400 } });
    await expect(page.getByLabel("Open navigation menu")).toBeVisible();
    await expect(page.getByTestId("chat-panel")).toBeVisible();
  });
});
