import { expect, test, type Page } from "@playwright/test";

// US-023 / AC-076..080: the blue (#4285F4) -> purple (#9168C0) accent
// palette applied through the existing `--brand-primary` / `--brand-accent`
// CSS custom properties and the `brand` token object, rather than through
// any new component, class, or hand-picked Tailwind color utility.
//
// Every network call this file makes is intercepted with `page.route`
// against a minimal in-memory fixture (the empty-thread-list case needs
// nothing more) -- nothing here reaches a real backend, a live Gemini
// call, or MinIO. The Setup screen calls no API at all, so those tests
// mock nothing.

const PRIMARY_RGB = "rgb(66, 133, 244)"; // #4285F4
const ACCENT_RGB = "rgb(145, 104, 192)"; // #9168C0
const OLD_NEUTRAL_HIGHLIGHT_RGB = "rgb(241, 245, 249)"; // Tailwind slate-100

async function mockEmptyThreadList(page: Page) {
  await page.route("**/threads", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
      return;
    }
    await route.continue();
  });
}

function parseRgb(value: string): [number, number, number] {
  const match = value.match(/(\d+),\s*(\d+),\s*(\d+)/);
  if (!match) throw new Error(`Could not parse rgb() value: ${value}`);
  return [Number(match[1]), Number(match[2]), Number(match[3])];
}

/** True only for a genuinely blue/purple-*tinted* color -- the blue channel
 * strictly largest AND enough spread between the channels (chroma > 30) to
 * rule out a near-neutral gray like Tailwind's slate-100 (#f1f5f9), whose
 * blue channel is technically largest too (249 vs 241/245) but by a margin
 * far too small to read as "accent-colored" to a person looking at it.
 * #4285F4 (chroma 178) and #9168C0 (chroma 88) both clear this easily;
 * slate-100 (chroma 8) does not. */
function hasBlueOrPurpleAccentTint(rgbString: string): boolean {
  const [r, g, b] = parseRgb(rgbString);
  const chroma = Math.max(r, g, b) - Math.min(r, g, b);
  return b > r && b > g && chroma > 30;
}

test.describe("AC-080: the change is token values only, read from the documented custom properties", () => {
  test("--brand-primary and --brand-accent resolve to the new palette on the root element", async ({
    page,
  }) => {
    await mockEmptyThreadList(page);
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

test.describe("AC-076: primary action buttons use the new blue/purple accent, unchanged otherwise", () => {
  test("the empty-state 'New conversation' button renders with the new primary color at its usual size", async ({
    page,
  }) => {
    await mockEmptyThreadList(page);
    await page.goto("/chat");

    const button = page.getByRole("button", { name: "New conversation" }).last();
    await expect(button).toBeVisible();
    await expect(button).toHaveCSS("background-color", PRIMARY_RGB);

    // Unchanged size/position expectations: still a compact, single-line
    // action button with its label intact, not stretched or relabelled.
    const box = await button.boundingBox();
    expect(box).not.toBeNull();
    expect(box!.height).toBeGreaterThan(20);
    expect(box!.height).toBeLessThan(60);
    await expect(button).toHaveText(/new conversation/i);
  });

  test("the chat composer's 'Send' button renders with the new primary color at its usual size", async ({
    page,
  }) => {
    await mockEmptyThreadList(page);
    await page.goto("/chat");

    const sendButton = page.getByRole("button", { name: /^send$/i });
    await expect(sendButton).toBeVisible();
    await expect(sendButton).toHaveCSS("background-color", PRIMARY_RGB);

    const box = await sendButton.boundingBox();
    expect(box).not.toBeNull();
    expect(box!.height).toBeGreaterThan(20);
    expect(box!.height).toBeLessThan(60);
  });
});

test.describe("AC-077: a text link styled with the primary/accent token resolves to the new value", () => {
  test("the Setup screen's footer 'Documents' link uses the accent token verbatim", async ({
    page,
  }) => {
    await page.goto("/setup");

    const link = page.locator("footer").getByRole("button", { name: /^documents$/i });
    await expect(link).toBeVisible();
    await expect(link).toHaveCSS("color", ACCENT_RGB);
  });

  test("the Setup screen's footer 'Ask a question' link uses the accent token verbatim", async ({
    page,
  }) => {
    await page.goto("/setup");

    const link = page.locator("footer").getByRole("button", { name: /ask a question/i });
    await expect(link).toBeVisible();
    await expect(link).toHaveCSS("color", ACCENT_RGB);
  });
});

test.describe("AC-078: the active/selected element is highlighted with the new accent color", () => {
  test("the active Setup-screen tab is highlighted with the new primary color, the inactive tabs are not", async ({
    page,
  }) => {
    await page.goto("/setup");

    const localTab = page.getByRole("tab", { name: "Run it locally" });
    const deployTab = page.getByRole("tab", { name: "Deploy it" });

    await expect(localTab).toHaveCSS("background-color", PRIMARY_RGB);
    await expect(deployTab).not.toHaveCSS("background-color", PRIMARY_RGB);

    await deployTab.click();

    await expect(deployTab).toHaveCSS("background-color", PRIMARY_RGB);
    await expect(localTab).not.toHaveCSS("background-color", PRIMARY_RGB);
  });

  test("the currently open thread in the sidebar is highlighted with the new blue/purple accent, not the old neutral gray", async ({
    page,
  }) => {
    const threadId = "99999999-9999-9999-9999-999999999999";
    await page.route("**/threads", async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify([
            { id: threadId, title: "Office holidays", last_active_at: new Date().toISOString() },
          ]),
        });
        return;
      }
      await route.continue();
    });
    await page.route(`**/threads/${threadId}`, async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ id: threadId, title: "Office holidays", messages: [] }),
        });
        return;
      }
      await route.continue();
    });

    await page.goto("/chat");
    await page.getByRole("button", { name: "Office holidays" }).click();

    const activeRow = page
      .getByRole("button", { name: "Office holidays" })
      .locator("xpath=ancestor::div[1]");
    const highlightColor = await activeRow.evaluate((el) => getComputedStyle(el).backgroundColor);

    expect(
      highlightColor,
      "the open thread's sidebar row must not keep the old neutral gray highlight",
    ).not.toBe(OLD_NEUTRAL_HIGHLIGHT_RGB);
    expect(
      hasBlueOrPurpleAccentTint(highlightColor),
      `expected a visibly blue/purple-tinted highlight (not a near-neutral gray), got ${highlightColor}`,
    ).toBe(true);
  });
});

test.describe("AC-079: only the accent/primary tokens change -- backgrounds, spacing and layout do not", () => {
  test("the app background and corner-radius tokens are untouched by the accent change, across screens", async ({
    page,
  }) => {
    await mockEmptyThreadList(page);
    await page.goto("/chat");

    const chatTokens = await page.evaluate(() => {
      const style = getComputedStyle(document.documentElement);
      return {
        background: style.getPropertyValue("--brand-background").trim(),
        radius: style.getPropertyValue("--brand-radius").trim(),
        surface: style.getPropertyValue("--brand-surface").trim(),
      };
    });

    await page.goto("/documents");
    const documentsTokens = await page.evaluate(() => {
      const style = getComputedStyle(document.documentElement);
      return {
        background: style.getPropertyValue("--brand-background").trim(),
        radius: style.getPropertyValue("--brand-radius").trim(),
        surface: style.getPropertyValue("--brand-surface").trim(),
      };
    });

    expect(documentsTokens).toEqual(chatTokens);
    expect(chatTokens.background.toLowerCase()).toBe("#fffbf2");
    expect(chatTokens.radius).toBe("0.5rem");

    // This application ships one theme only (no dark-mode toggle exists in
    // the shell), so the dark-mode half of AC-079 cannot be executed here
    // and is left PENDING rather than asserted against non-existent UI.
  });
});
