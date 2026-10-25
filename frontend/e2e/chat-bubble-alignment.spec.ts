import { expect, test, type Locator, type Page } from "@playwright/test";

// US-022-2 / AC-071..075: chat bubble alignment (user right, assistant left)
// holds during streaming, with long/citation-bearing content, at mobile
// widths, and across reopened history. Every network call in this file is
// intercepted with `page.route` against small in-memory fixtures -- nothing
// here reaches a real backend, a live Gemini call, or MinIO.
//
// Alignment is asserted via bounding-box comparison against the message
// row's own box (the flex container that actually carries the
// justify-end/justify-start alignment), never via Tailwind class strings.

const TOLERANCE_PX = 2;

async function boxOf(locator: Locator) {
  const box = await locator.boundingBox();
  expect(box, "expected element to have a bounding box (it must be visible)").not.toBeNull();
  return box!;
}

/** Asserts a single message row's bubble hugs the correct edge of its row. */
async function assertRowAlignment(row: Locator) {
  const role = await row.getAttribute("data-role");
  const rowBox = await boxOf(row);
  const bubbleBox = await boxOf(row.locator('[data-testid="message-bubble"]'));

  // The bubble never exceeds its row's horizontal bounds (no overflow).
  expect(bubbleBox.x).toBeGreaterThanOrEqual(rowBox.x - TOLERANCE_PX);
  expect(bubbleBox.x + bubbleBox.width).toBeLessThanOrEqual(
    rowBox.x + rowBox.width + TOLERANCE_PX,
  );

  if (role === "user") {
    expect(
      Math.abs(bubbleBox.x + bubbleBox.width - (rowBox.x + rowBox.width)),
    ).toBeLessThanOrEqual(TOLERANCE_PX);
  } else {
    expect(Math.abs(bubbleBox.x - rowBox.x)).toBeLessThanOrEqual(TOLERANCE_PX);
  }
}

function makeMessage(
  id: string,
  role: "user" | "assistant",
  content: string,
  citations: unknown[] = [],
  status = "complete",
) {
  return { id, role, content, status, citations };
}

async function mockThreadRoutes(
  page: Page,
  threadId: string,
  state: {
    threads: Array<{ id: string; title: string; last_active_at: string }>;
    detail: { id: string; title: string; messages: unknown[] };
    streamBody?: string;
  },
) {
  await page.route("**/threads", async (route) => {
    const method = route.request().method();
    if (method === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(state.threads),
      });
      return;
    }
    if (method === "POST") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: threadId,
          title: "New conversation",
          created_at: new Date().toISOString(),
        }),
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
        body: JSON.stringify(state.detail),
      });
      return;
    }
    await route.continue();
  });

  if (state.streamBody !== undefined) {
    await page.route(`**/threads/${threadId}/messages`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body: state.streamBody!,
      });
    });
  }
}

test.describe("AC-071: alternating user/assistant alignment, opposite sides", () => {
  const THREAD_ID = "a0000000-0000-0000-0000-000000000001";

  test("every user bubble aligns right, every assistant bubble aligns left, and the two sides differ", async ({
    page,
  }) => {
    const messages = [
      makeMessage("m1", "user", "What's the per-head limit for client dinners?"),
      makeMessage("m2", "assistant", "The per-head limit for client dinners is €60."),
      makeMessage("m3", "user", "Does that include drinks?"),
      makeMessage("m4", "assistant", "Yes, the €60 limit is inclusive of drinks."),
    ];
    await mockThreadRoutes(page, THREAD_ID, {
      threads: [{ id: THREAD_ID, title: "Dinners", last_active_at: new Date().toISOString() }],
      detail: { id: THREAD_ID, title: "Dinners", messages },
    });

    await page.goto(`/chat?thread=${THREAD_ID}`);
    const rows = page.getByTestId("message-row");
    await expect(rows).toHaveCount(messages.length);

    // All rows share the same horizontal column bounds.
    const boxes = await Promise.all(
      (await rows.all()).map((row) => boxOf(row)),
    );
    const firstBox = boxes[0];
    for (const box of boxes) {
      expect(Math.abs(box.x - firstBox.x)).toBeLessThanOrEqual(TOLERANCE_PX);
      expect(Math.abs(box.x + box.width - (firstBox.x + firstBox.width))).toBeLessThanOrEqual(
        TOLERANCE_PX,
      );
    }

    for (const row of await rows.all()) {
      await assertRowAlignment(row);
    }

    const userBubbleBox = await boxOf(
      rows.filter({ has: page.locator('[data-role="user"]') }).first().locator('[data-testid="message-bubble"]'),
    );
    const assistantBubbleBox = await boxOf(
      rows
        .filter({ has: page.locator('[data-role="assistant"]') })
        .first()
        .locator('[data-testid="message-bubble"]'),
    );
    expect(Math.abs(userBubbleBox.x - assistantBubbleBox.x)).toBeGreaterThan(50);
  });
});

test.describe("AC-072: streaming assistant bubble stays left-aligned", () => {
  const THREAD_ID = "a0000000-0000-0000-0000-000000000002";

  test("left edge is constant as tokens append and after the final event", async ({ page }) => {
    const pieces = ["Employees get ", "25 days of ", "annual leave each year."];
    const fullAnswer = pieces.join("");
    const messageId = "b0000000-0000-0000-0000-000000000099";
    const streamBody =
      pieces.map((text) => `event: token\ndata: ${JSON.stringify({ text })}\n\n`).join("") +
      `event: final\ndata: ${JSON.stringify({ message_id: messageId, citations: [] })}\n\n`;

    const state = {
      threads: [] as Array<{ id: string; title: string; last_active_at: string }>,
      detail: {
        id: THREAD_ID,
        title: "Leave policy",
        messages: [
          makeMessage("m1", "user", "How many leave days do employees get?"),
          makeMessage(messageId, "assistant", fullAnswer),
        ],
      },
      streamBody,
    };
    await mockThreadRoutes(page, THREAD_ID, state);

    await page.goto("/chat");
    await page
      .getByPlaceholder("Ask a question about the documents…")
      .fill("How many leave days do employees get?");
    await page.getByRole("button", { name: /^send$/i }).click();

    const streamingRow = page.locator('[data-testid="message-row"][data-role="assistant"]');
    await expect(streamingRow.locator('[data-testid="message-bubble"]')).toContainText(
      pieces[0],
      { timeout: 10_000 },
    );
    const earlyBox = await boxOf(streamingRow);
    const earlyBubbleBox = await boxOf(streamingRow.locator('[data-testid="message-bubble"]'));
    expect(Math.abs(earlyBubbleBox.x - earlyBox.x)).toBeLessThanOrEqual(TOLERANCE_PX);

    await expect(page.getByText(fullAnswer)).toBeVisible();
    const finalRow = page.locator('[data-testid="message-row"][data-role="assistant"]').last();
    const finalRowBox = await boxOf(finalRow);
    const finalBubbleBox = await boxOf(finalRow.locator('[data-testid="message-bubble"]'));
    expect(Math.abs(finalBubbleBox.x - finalRowBox.x)).toBeLessThanOrEqual(TOLERANCE_PX);
    // The left edge did not drift while the content grew.
    expect(Math.abs(finalBubbleBox.x - earlyBubbleBox.x)).toBeLessThanOrEqual(TOLERANCE_PX);
  });
});

test.describe("AC-073: long answer with citations stays within bounds and aligned", () => {
  const THREAD_ID = "a0000000-0000-0000-0000-000000000003";

  test("no horizontal overflow of the bubble, and alignment holds after expanding citations", async ({
    page,
  }) => {
    const longAnswer = [
      "Paragraph one covers the general expense policy for client-facing meals and explains that the per-head limit applies regardless of seniority.",
      "Paragraph two covers travel reimbursement, noting that economy class is standard for flights under six hours and business class requires manager pre-approval.",
      "Paragraph three covers the approval workflow end to end, from the initial request through finance sign-off and the eventual reimbursement payment run.",
    ].join("\n\n");
    const citations = [
      {
        id: "cit-1",
        document_name: "https://intranet.example.com/policies/expenses-and-travel-handbook-2026.pdf",
        source_location: "p. 14",
        excerpt:
          "The per-head limit for client dinners is €60 inclusive of drinks and applies to all staff grades without exception.",
        document_available: true,
      },
    ];
    const THREAD_TITLE = "Expense policy";
    await mockThreadRoutes(page, THREAD_ID, {
      threads: [{ id: THREAD_ID, title: THREAD_TITLE, last_active_at: new Date().toISOString() }],
      detail: {
        id: THREAD_ID,
        title: THREAD_TITLE,
        messages: [
          makeMessage("m1", "user", "Summarise the expense and travel policy."),
          makeMessage("m2", "assistant", longAnswer, citations),
        ],
      },
    });

    await page.goto(`/chat?thread=${THREAD_ID}`);
    const assistantRow = page.locator('[data-testid="message-row"][data-role="assistant"]');
    await expect(assistantRow).toBeVisible();
    await assertRowAlignment(assistantRow);

    const hasHorizontalOverflow = await page.evaluate(
      () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
    );
    expect(hasHorizontalOverflow).toBe(false);

    const toggle = page.getByRole("button", { name: /expenses-and-travel-handbook/ });
    await toggle.click();
    await expect(page.getByText(/per-head limit for client dinners is €60/)).toBeVisible();

    // Still contained and still left-aligned after the citation panel grew.
    await assertRowAlignment(assistantRow);
    const afterExpandOverflow = await page.evaluate(
      () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
    );
    expect(afterExpandOverflow).toBe(false);
  });
});

test.describe("AC-074: mobile viewport keeps bubbles on their side with no horizontal scroll", () => {
  const THREAD_ID = "a0000000-0000-0000-0000-000000000004";
  test.use({ viewport: { width: 375, height: 700 } });

  test("no document horizontal scrolling and both bubble sides stay fully visible", async ({
    page,
  }) => {
    const messages = [
      makeMessage("m1", "user", "Which laptops are approved for contractors?"),
      makeMessage(
        "m2",
        "assistant",
        "Contractors are approved for the standard 13-inch business laptop model only.",
      ),
    ];
    await mockThreadRoutes(page, THREAD_ID, {
      threads: [{ id: THREAD_ID, title: "Laptops", last_active_at: new Date().toISOString() }],
      detail: { id: THREAD_ID, title: "Laptops", messages },
    });

    await page.goto(`/chat?thread=${THREAD_ID}`);
    const rows = page.getByTestId("message-row");
    await expect(rows).toHaveCount(messages.length);

    const hasHorizontalOverflow = await page.evaluate(
      () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
    );
    expect(hasHorizontalOverflow).toBe(false);

    for (const row of await rows.all()) {
      await assertRowAlignment(row);
      const bubbleBox = await boxOf(row.locator('[data-testid="message-bubble"]'));
      expect(bubbleBox.x).toBeGreaterThanOrEqual(0);
      expect(bubbleBox.x + bubbleBox.width).toBeLessThanOrEqual(375 + TOLERANCE_PX);
    }
  });
});

test.describe("AC-075: 20+ message history keeps every bubble on its correct side", () => {
  const THREAD_ID = "a0000000-0000-0000-0000-000000000005";

  test("first and last bubbles (and everything between) match their role's alignment", async ({
    page,
  }) => {
    const messages: unknown[] = [];
    const total = 24;
    for (let i = 0; i < total; i += 1) {
      const role = i % 2 === 0 ? "user" : "assistant";
      messages.push(
        makeMessage(
          `m${i}`,
          role,
          role === "user" ? `Question number ${i + 1}?` : `Answer number ${i + 1}.`,
        ),
      );
    }
    await mockThreadRoutes(page, THREAD_ID, {
      threads: [{ id: THREAD_ID, title: "Long history", last_active_at: new Date().toISOString() }],
      detail: { id: THREAD_ID, title: "Long history", messages },
    });

    await page.goto(`/chat?thread=${THREAD_ID}`);
    const rows = page.getByTestId("message-row");
    await expect(rows).toHaveCount(total);

    const allRows = await rows.all();
    await assertRowAlignment(allRows[0]);
    await assertRowAlignment(allRows[allRows.length - 1]);
    for (const row of allRows) {
      await assertRowAlignment(row);
    }
  });
});
