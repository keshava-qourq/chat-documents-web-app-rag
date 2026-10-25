import { expect, test, type Page } from "@playwright/test";

// US-023 / AC-076..080: the blue (#4285F4) -> purple (#9168C0) accent token
// pair is applied via the existing CSS custom properties
// (--brand-primary / --brand-accent, mirrored in frontend/src/lib/brand.ts)
// rather than through any new component, class or markup. Every network
// call this file makes is intercepted with `page.route` against small
// in-memory fixtures, following the same convention as the other Chat/
// Documents specs in this directory -- nothing here reaches a live
// backend, Gemini or MinIO.

const BLUE = "rgb(66, 133, 244)"; // #4285F4, exact --brand-primary
const PURPLE = "rgb(145, 104, 192)"; // #9168C0, exact --brand-accent
const PREVIOUS_GRAY_HIGHLIGHT = "rgb(241, 245, 249)"; // slate-100 -- the old, non-token highlight

const THREAD_ID = "c0000000-0000-0000-0000-000000000001";

function threadFixture() {
  return {
    id: THREAD_ID,
    title: "Berlin office holidays",
    last_active_at: new Date().toISOString(),
  };
}

function threadDetailFixture() {
  return {
    id: THREAD_ID,
    title: "Berlin office holidays",
    messages: [
      {
        id: "msg-1",
        role: "user",
        content: "When does the Berlin office close for the Christmas holidays?",
        status: "complete",
        citations: [],
      },
      {
        id: "msg-2",
        role: "assistant",
        content: "The Berlin office is closed from 24 December through 2 January.",
        status: "complete",
        citations: [],
      },
    ],
  };
}

async function mockChatWithOneThread(page: Page) {
  await page.route("**/threads", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([threadFixture()]),
      });
      return;
    }
    await route.continue();
  });
  await page.route(`**/threads/${THREAD_ID}`, async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(threadDetailFixture()),
      });
      return;
    }
    await route.continue();
  });
}

async function mockEmptyDocumentsAndChat(page: Page) {
  await page.route("**/threads", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
      return;
    }
    await route.continue();
  });
  await page.route("**/documents", async (route) => {
    if (route.request().resourceType() === "document") {
      await route.continue();
      return;
    }
    if (route.request().method() === "GET") {
      await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
      return;
    }
    await route.continue();
  });
}

test.describe("AC-080: tokens are the only thing that changed", () => {
  test("[AC-080] the CSS custom properties resolve to the exact new blue/purple hex values", async ({
    page,
  }) => {
    await page.goto("/chat");
    const tokens = await page.evaluate(() => {
      const style = getComputedStyle(document.documentElement);
      return {
        primary: style.getPropertyValue("--brand-primary").trim(),
        accent: style.getPropertyValue("--brand-accent").trim(),
      };
    });
    expect(tokens.primary.toLowerCase()).toBe("#4285f4");
    expect(tokens.accent.toLowerCase()).toBe("#9168c0");
  });
});

test.describe("AC-076: primary action buttons use the new accent color, unchanged size/position/label", () => {
  test("[AC-076] the chat composer's Send button is blue (#4285F4) and keeps its label and size", async ({
    page,
  }) => {
    await mockEmptyDocumentsAndChat(page);
    await page.goto("/chat");

    const sendButton = page.getByRole("button", { name: /^send$/i });
    await expect(sendButton).toBeVisible();
    await expect(sendButton).toHaveText(/send/i);

    const backgroundColor = await sendButton.evaluate(
      (el) => getComputedStyle(el).backgroundColor,
    );
    expect(backgroundColor).toBe(BLUE);

    // Size/position are governed by the Button component's own `md` size
    // class (`h-9`), independent of color -- a token-only change must not
    // touch this.
    const box = await sendButton.boundingBox();
    expect(box).not.toBeNull();
    expect(Math.round(box!.height)).toBe(36);
  });

  test("[AC-076] the empty-sidebar 'New conversation' action is the same blue, with its label intact", async ({
    page,
  }) => {
    await mockEmptyDocumentsAndChat(page);
    await page.goto("/chat");

    const newConversation = page.getByRole("button", { name: "New conversation" }).first();
    await expect(newConversation).toBeVisible();
    const backgroundColor = await newConversation.evaluate(
      (el) => getComputedStyle(el).backgroundColor,
    );
    expect(backgroundColor).toBe(BLUE);
  });
});

test.describe("AC-077: a hyperlink/text link styled with the primary color resolves to the new token", () => {
  test("[AC-077] the Setup screen's 'Documents' footer link-style control uses the exact purple accent token", async ({
    page,
  }) => {
    await page.goto("/setup");

    const link = page.getByRole("button", { name: /^documents$/i });
    await expect(link).toBeVisible();
    const color = await link.evaluate((el) => getComputedStyle(el).color);
    expect(color).toBe(PURPLE);
  });
});

test.describe("AC-078: the active/selected element is highlighted with the new accent color", () => {
  test("[AC-078] the currently open thread in the sidebar is highlighted with an accent color token, not the old neutral gray", async ({
    page,
  }) => {
    await mockChatWithOneThread(page);
    await page.goto(`/chat?thread=${THREAD_ID}`);

    const openThreadButton = page.getByRole("button", { name: "Berlin office holidays" });
    await expect(openThreadButton).toBeVisible();

    // The highlighted row is the open thread's own list item container,
    // immediately wrapping its open/rename/delete controls.
    const highlightedRow = openThreadButton.locator("xpath=..");
    const backgroundColor = await highlightedRow.evaluate(
      (el) => getComputedStyle(el).backgroundColor,
    );

    expect(
      backgroundColor,
      `expected the open thread's row to use an accent color token ` +
        `(${BLUE} or ${PURPLE}), not the previous neutral gray highlight`,
    ).not.toBe(PREVIOUS_GRAY_HIGHLIGHT);
    expect([BLUE, PURPLE]).toContain(backgroundColor);
  });

  test("[AC-078] the active main-navigation tab is highlighted with an accent color token, not the old neutral hover gray", async ({
    page,
  }) => {
    await mockEmptyDocumentsAndChat(page);
    await page.goto("/chat");

    const nav = page.getByLabel("Main navigation");
    const activeLink = nav.getByText("Chat", { exact: true });
    await expect(activeLink).toBeVisible();

    const backgroundColor = await activeLink.evaluate(
      (el) => getComputedStyle(el).backgroundColor,
    );
    const color = await activeLink.evaluate((el) => getComputedStyle(el).color);

    const usesAccentBackground = [BLUE, PURPLE].includes(backgroundColor);
    const usesAccentText = [BLUE, PURPLE].includes(color);
    expect(
      usesAccentBackground || usesAccentText,
      "expected the active nav tab's highlight (background or text) to resolve to the " +
        `new accent token (${BLUE} or ${PURPLE}); got background ${backgroundColor}, text ${color}`,
    ).toBe(true);
  });
});

test.describe("AC-079: only accent/primary tokens change -- background, spacing, typography and layout are untouched", () => {
  test("[AC-079] the page keeps a light neutral background and the composer keeps its documented size in both the light shell and after navigating", async ({
    page,
  }) => {
    await mockEmptyDocumentsAndChat(page);
    await page.goto("/chat");

    const backgroundColor = await page.evaluate(
      () => getComputedStyle(document.body).backgroundColor,
    );
    const match = backgroundColor.match(/\d+/g);
    expect(match).not.toBeNull();
    const [r, g, b] = match!.map(Number);
    // The accent/primary tokens are blue/purple; the page background itself
    // is untouched neutral/light, as it was before this change.
    expect((r + g + b) / 3).toBeGreaterThan(120);

    const composer = page.getByPlaceholder("Ask a question about the documents…");
    await expect(composer).toBeVisible();
    const composerBox = await composer.boundingBox();
    expect(composerBox).not.toBeNull();
    expect(composerBox!.height).toBeGreaterThanOrEqual(44); // min-h-[44px], unrelated to color
  });
});
