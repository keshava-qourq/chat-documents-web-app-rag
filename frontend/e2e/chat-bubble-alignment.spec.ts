import { expect, test, type Locator, type Page } from "@playwright/test";

// US-022-2 / AC-071..075: user bubbles align to the chat column's right
// edge, assistant bubbles align to its left edge, and that holds while
// streaming, with long/citation-heavy content, on mobile widths, and across
// a reopened long thread history. Every network call below is intercepted
// with `page.route` against small in-memory fixtures (following the style
// in chat-streaming.spec.ts) -- nothing here reaches a real backend, a live
// Gemini call, or MinIO.
//
// The "chat column" boundary is read from each bubble's own row (the <li>
// that wraps it, which spans the full width of the chat column via
// `flex w-full`) rather than from a specific class name, per the geometry
// constraint: a user bubble's right edge must match its row's right edge,
// and an assistant bubble's left edge must match its row's left edge.

const TOLERANCE_PX = 2;

const THREAD_ID = "55555555-5555-5555-5555-555555555555";
const STREAM_THREAD_ID = "66666666-6666-6666-6666-666666666666";
const STREAM_MESSAGE_ID = "77777777-7777-7777-7777-777777777777";

function threadDetail(id: string, title: string, messages: unknown[]) {
  return { id, title, messages };
}

function userMessage(id: string, content: string) {
  return { id, role: "user", content, status: "complete", citations: [] };
}

function assistantMessage(
  id: string,
  content: string,
  opts: { status?: string; citations?: unknown[] } = {},
) {
  return {
    id,
    role: "assistant",
    content,
    status: opts.status ?? "complete",
    citations: opts.citations ?? [],
  };
}

async function mockThreadGet(
  page: Page,
  threadId: string,
  summary: { id: string; title: string; last_active_at: string },
  detail: ReturnType<typeof threadDetail>,
) {
  await page.route("**/threads", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([summary]),
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
        body: JSON.stringify(detail),
      });
      return;
    }
    await route.continue();
  });
}

/**
 * Asserts, for every `[data-testid="message-bubble"]` currently rendered,
 * that its role-appropriate edge matches its own row's edge within a small
 * pixel tolerance -- a user bubble's right edge to the row's right edge, an
 * assistant bubble's left edge to the row's left edge.
 */
async function assertAllBubblesAligned(page: Page) {
  const bubbles = page.getByTestId("message-bubble");
  const count = await bubbles.count();
  expect(count).toBeGreaterThan(0);

  for (let i = 0; i < count; i++) {
    const bubble = bubbles.nth(i);
    const role = await bubble.getAttribute("data-role");
    const row: Locator = bubble.locator("xpath=..");
    const bubbleBox = await bubble.boundingBox();
    const rowBox = await row.boundingBox();
    expect(bubbleBox, `bubble ${i} has no bounding box`).not.toBeNull();
    expect(rowBox, `row for bubble ${i} has no bounding box`).not.toBeNull();
    if (!bubbleBox || !rowBox) continue;

    if (role === "user") {
      const bubbleRight = bubbleBox.x + bubbleBox.width;
      const rowRight = rowBox.x + rowBox.width;
      expect(
        Math.abs(bubbleRight - rowRight),
        `user bubble ${i} right edge (${bubbleRight}) should match row right edge (${rowRight})`,
      ).toBeLessThanOrEqual(TOLERANCE_PX);
    } else if (role === "assistant") {
      expect(
        Math.abs(bubbleBox.x - rowBox.x),
        `assistant bubble ${i} left edge (${bubbleBox.x}) should match row left edge (${rowBox.x})`,
      ).toBeLessThanOrEqual(TOLERANCE_PX);
    } else {
      throw new Error(`unexpected data-role "${role}" on bubble ${i}`);
    }
  }
}

test.describe("AC-071: alternating turns align consistently to their own edge", () => {
  test("every user bubble's right edge and every assistant bubble's left edge match the chat column's boundary", async ({
    page,
  }) => {
    const summary = { id: THREAD_ID, title: "Alignment check", last_active_at: new Date().toISOString() };
    const detail = threadDetail(THREAD_ID, "Alignment check", [
      userMessage("m1", "What is the client dinner limit?"),
      assistantMessage("m2", "The per-head limit for client dinners is €60."),
      userMessage("m3", "And for team lunches?"),
      assistantMessage("m4", "Team lunches are capped at €25 per head."),
      userMessage("m5", "Thanks, one more: contractor laptops?"),
      assistantMessage("m6", "Contractors may use any laptop meeting the security policy."),
    ]);
    await mockThreadGet(page, THREAD_ID, summary, detail);

    await page.goto("/chat");
    await page.getByRole("button", { name: "Alignment check" }).click();
    await expect(page.getByText("Contractors may use any laptop meeting the security policy.")).toBeVisible();

    await assertAllBubblesAligned(page);
  });
});

test.describe("AC-072: the assistant bubble's left edge is stable while streaming", () => {
  test("left edge x-coordinate is unchanged between an early token render and the completed answer, while the bubble grows", async ({
    page,
  }) => {
    // Many short pieces so the first rendered state is a single short word
    // (a small bubble) and the completed answer wraps across several lines
    // (a visibly taller bubble), making a height/width change observable
    // regardless of how the mocked body is chunked by the browser.
    const words = [
      "Employees",
      "who",
      "relocate",
      "to",
      "a",
      "different",
      "country",
      "office",
      "receive",
      "a",
      "one-time",
      "relocation",
      "allowance",
      "equal",
      "to",
      "two",
      "months",
      "of",
      "their",
      "gross",
      "salary",
      "at",
      "the",
      "new",
      "location,",
      "paid",
      "out",
      "within",
      "the",
      "first",
      "pay",
      "cycle",
      "after",
      "the",
      "move",
      "is",
      "confirmed",
      "by",
      "HR.",
    ];
    const pieces = words.map((w, i) => (i === 0 ? w : ` ${w}`));
    const fullAnswer = pieces.join("");

    const summary = {
      id: STREAM_THREAD_ID,
      title: "New conversation",
      last_active_at: new Date().toISOString(),
    };
    const detail = threadDetail(STREAM_THREAD_ID, "Relocation allowance", [
      userMessage("m1", "What is the relocation allowance?"),
      assistantMessage(STREAM_MESSAGE_ID, fullAnswer),
    ]);

    const tokenEvents = pieces
      .map((text) => `event: token\ndata: ${JSON.stringify({ text })}\n\n`)
      .join("");
    const finalEvent = `event: final\ndata: ${JSON.stringify({
      message_id: STREAM_MESSAGE_ID,
      citations: [],
    })}\n\n`;
    const streamBody = tokenEvents + finalEvent;

    await page.route("**/threads", async (route) => {
      const method = route.request().method();
      if (method === "GET") {
        await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) });
        return;
      }
      if (method === "POST") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            id: STREAM_THREAD_ID,
            title: "New conversation",
            created_at: new Date().toISOString(),
          }),
        });
        return;
      }
      await route.continue();
    });
    await page.route(`**/threads/${STREAM_THREAD_ID}`, async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(detail) });
        return;
      }
      await route.continue();
    });
    await page.route(`**/threads/${STREAM_THREAD_ID}/messages`, async (route) => {
      await route.fulfill({ status: 200, contentType: "text/event-stream", body: streamBody });
    });

    await page.goto("/chat");
    await page
      .getByPlaceholder("Ask a question about the documents…")
      .fill("What is the relocation allowance?");
    await page.getByRole("button", { name: /^send$/i }).click();

    const assistantBubble = page.getByTestId("message-bubble").filter({ hasText: words[0] }).last();
    await expect(assistantBubble).toBeVisible();
    const earlyBox = await assistantBubble.boundingBox();
    expect(earlyBox).not.toBeNull();

    await expect(page.getByText(fullAnswer)).toBeVisible();
    const finalBubble = page.getByTestId("message-bubble").filter({ hasText: words[0] }).last();
    const finalBox = await finalBubble.boundingBox();
    expect(finalBox).not.toBeNull();
    if (!earlyBox || !finalBox) return;

    expect(Math.abs(earlyBox.x - finalBox.x)).toBeLessThanOrEqual(TOLERANCE_PX);
    expect(finalBox.height).toBeGreaterThan(earlyBox.height);
  });
});

test.describe("AC-073: long multi-line content with citations and an unbroken long token stays within the chat column", () => {
  test("bubble bounding box stays within the chat column width and the page does not scroll horizontally", async ({
    page,
  }) => {
    const longUnbrokenToken = "x".repeat(220);
    const longAnswer = [
      "Here is a detailed breakdown of the relocation policy across every eligible region, ",
      "covering allowances, timelines and the documentation required before reimbursement.\n\n",
      "- Europe: two months' gross salary, paid within one pay cycle.\n",
      "- APAC: one and a half months' gross salary, paid within two pay cycles.\n",
      "- Americas: two months' gross salary plus a one-time shipping stipend.\n\n",
      `Reference code: ${longUnbrokenToken}\n\n`,
      "Submit the relocation form within thirty days of the confirmed move date.",
    ].join("");

    const citations = [
      {
        id: "cit-1",
        document_name: "relocation-policy.pdf",
        source_location: "p. 2",
        excerpt: "Two months' gross salary, paid within one pay cycle.",
        document_available: true,
      },
    ];

    const summary = { id: THREAD_ID, title: "Relocation policy", last_active_at: new Date().toISOString() };
    const detail = threadDetail(THREAD_ID, "Relocation policy", [
      userMessage("m1", "Give me the full relocation policy breakdown."),
      assistantMessage("m2", longAnswer, { citations }),
    ]);
    await mockThreadGet(page, THREAD_ID, summary, detail);

    await page.goto("/chat");
    await page.getByRole("button", { name: "Relocation policy" }).click();
    await expect(page.getByText(/Submit the relocation form/)).toBeVisible();

    const bubble = page.getByTestId("message-bubble").filter({ hasText: "Reference code" });
    const bubbleBox = await bubble.boundingBox();
    expect(bubbleBox).not.toBeNull();

    const chatPanel = page.getByTestId("chat-panel");
    const chatPanelBox = await chatPanel.boundingBox();
    expect(chatPanelBox).not.toBeNull();
    if (!bubbleBox || !chatPanelBox) return;

    expect(bubbleBox.x).toBeGreaterThanOrEqual(chatPanelBox.x - TOLERANCE_PX);
    expect(bubbleBox.x + bubbleBox.width).toBeLessThanOrEqual(
      chatPanelBox.x + chatPanelBox.width + TOLERANCE_PX,
    );

    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
    );
    expect(overflow).toBe(false);

    await assertAllBubblesAligned(page);
  });
});

test.describe("AC-074: mobile viewport keeps alignment and no horizontal scroll", () => {
  test.use({ viewport: { width: 375, height: 812 } });

  test("at 375x812 there is no horizontal document scroll and both alignment rules still hold", async ({
    page,
  }) => {
    const summary = { id: THREAD_ID, title: "Mobile alignment check", last_active_at: new Date().toISOString() };
    const detail = threadDetail(THREAD_ID, "Mobile alignment check", [
      userMessage("m1", "What is the per-head limit for client dinners, and does it vary by country office?"),
      assistantMessage(
        "m2",
        "The per-head limit for client dinners is €60 across all offices, with no country-specific variation.",
      ),
      userMessage("m3", "And team lunches?"),
      assistantMessage("m4", "Team lunches are capped at €25 per head."),
    ]);
    await mockThreadGet(page, THREAD_ID, summary, detail);

    await page.goto("/chat");
    await page.getByRole("button", { name: "Mobile alignment check" }).click();
    await expect(page.getByText("Team lunches are capped at €25 per head.")).toBeVisible();

    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
    );
    expect(overflow).toBe(false);

    await assertAllBubblesAligned(page);
  });
});

test.describe("AC-075: reopening a long thread keeps every bubble aligned, including an incomplete answer", () => {
  test("every bubble in a 10+ message history satisfies the alignment rule for its role", async ({
    page,
  }) => {
    const topics = [
      "the client dinner limit",
      "approved contractor laptops",
      "parental leave top-up for Dutch staff",
      "the Berlin office holiday closure",
      "the relocation allowance",
    ];
    const messages: unknown[] = [];
    topics.forEach((topic, i) => {
      messages.push(userMessage(`u${i}`, `What is the policy on ${topic}?`));
      messages.push(assistantMessage(`a${i}`, `Here is the policy on ${topic}: see the handbook for details.`));
    });
    // Replace the final assistant turn with an incomplete one (AC-037-style
    // history), so the fixture has 10+ messages and ends mid-answer.
    messages[messages.length - 1] = assistantMessage("a-last", "Here is the policy on the relocation", {
      status: "incomplete",
    });
    expect(messages.length).toBeGreaterThanOrEqual(10);

    const summary = { id: THREAD_ID, title: "Long history", last_active_at: new Date().toISOString() };
    const detail = threadDetail(THREAD_ID, "Long history", messages);
    await mockThreadGet(page, THREAD_ID, summary, detail);

    await page.goto("/chat");
    await page.getByRole("button", { name: "Long history" }).click();
    await expect(page.getByText("This answer did not finish.")).toBeVisible();

    const bubbleCount = await page.getByTestId("message-bubble").count();
    expect(bubbleCount).toBe(messages.length);

    await assertAllBubblesAligned(page);
  });
});
