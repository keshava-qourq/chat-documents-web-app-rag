import { expect, test, type Page } from "@playwright/test";

// CHAT8EED1A-15-3 / AC-032..040: streamed answers, citation expansion, and
// the did-not-complete indicator. Every network call in this file is
// intercepted with `page.route` against small in-memory fixtures -- nothing
// here reaches a real backend, a live Gemini call, or MinIO. The mocked SSE
// body is delivered as a single `route.fulfill` body (Playwright has no API
// for a manually-paced chunked response), so the "grows progressively"
// assertion below checks that an early token's text is visible -- which
// holds whether the browser delivers that body in one piece or several --
// rather than asserting the exact number of renders in between.

const THREAD_ID = "33333333-3333-3333-3333-333333333333";
const MESSAGE_ID = "44444444-4444-4444-4444-444444444444";

const TOKEN_PIECES = ["Employees get ", "25 days of ", "annual leave each year."];
const FULL_ANSWER = TOKEN_PIECES.join("");

function sseBody(pieces: string[], citations: unknown[]): string {
  const tokenEvents = pieces
    .map((text) => `event: token\ndata: ${JSON.stringify({ text })}\n\n`)
    .join("");
  const finalEvent = `event: final\ndata: ${JSON.stringify({
    message_id: MESSAGE_ID,
    citations,
  })}\n\n`;
  return tokenEvents + finalEvent;
}

function threadDetail(messages: unknown[]) {
  return { id: THREAD_ID, title: "Leave policy", messages };
}

async function mockThreadsAndStream(
  page: Page,
  state: {
    threads: Array<{ id: string; title: string; last_active_at: string }>;
    detail: ReturnType<typeof threadDetail>;
    streamBody: string;
    messagesCalls: number;
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
          id: THREAD_ID,
          title: "New conversation",
          created_at: new Date().toISOString(),
        }),
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
        body: JSON.stringify(state.detail),
      });
      return;
    }
    await route.continue();
  });

  await page.route(`**/threads/${THREAD_ID}/messages`, async (route) => {
    state.messagesCalls += 1;
    await route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: state.streamBody,
    });
  });
}

test.describe("AC-035 / AC-036: streamed answers and citations", () => {
  test("answer text grows progressively and citations appear on completion", async ({ page }) => {
    const citations = [
      {
        id: "cit-1",
        document_name: "handbook.pdf",
        source_location: "p. 4",
        excerpt: "Employees are entitled to 25 days of annual leave each year.",
        document_available: true,
      },
    ];
    const state = {
      threads: [] as Array<{ id: string; title: string; last_active_at: string }>,
      detail: threadDetail([
        {
          id: "msg-user-1",
          role: "user",
          content: "How many leave days do employees get?",
          status: "complete",
          citations: [],
        },
        {
          id: MESSAGE_ID,
          role: "assistant",
          content: FULL_ANSWER,
          status: "complete",
          citations,
        },
      ]),
      streamBody: sseBody(TOKEN_PIECES, citations),
      messagesCalls: 0,
    };
    await mockThreadsAndStream(page, state);

    await page.goto("/chat");
    await page
      .getByPlaceholder("Ask a question about the documents…")
      .fill("How many leave days do employees get?");
    await page.getByRole("button", { name: /^send$/i }).click();

    // The first streamed piece appears before the request settles.
    await expect(page.getByText(TOKEN_PIECES[0], { exact: false }).first()).toBeVisible();

    // Once the stream completes and the persisted thread is re-fetched, the
    // full answer and its citation are shown (AC-036).
    await expect(page.getByText(FULL_ANSWER)).toBeVisible();
    await expect(page.getByText("handbook.pdf")).toBeVisible();
    expect(state.messagesCalls).toBe(1);
  });
});

test.describe("AC-032..034: citation expansion", () => {
  test("expands to show excerpt, file name and page/section, collapses unchanged, and shows deleted-source wording", async ({
    page,
  }) => {
    const citations = [
      {
        id: "cit-available",
        document_name: "handbook.pdf",
        source_location: "p. 4",
        excerpt: "Employees are entitled to 25 days of annual leave each year.",
        document_available: true,
      },
      {
        id: "cit-deleted",
        document_name: "old-policy.pdf",
        source_location: "p. 1",
        excerpt: "This excerpt belongs to a document that has since been removed.",
        document_available: false,
      },
    ];
    const state = {
      threads: [{ id: THREAD_ID, title: "Leave policy", last_active_at: new Date().toISOString() }],
      detail: threadDetail([
        {
          id: "msg-user-1",
          role: "user",
          content: "How many leave days do employees get?",
          status: "complete",
          citations: [],
        },
        {
          id: MESSAGE_ID,
          role: "assistant",
          content: FULL_ANSWER,
          status: "complete",
          citations,
        },
      ]),
      streamBody: "",
      messagesCalls: 0,
    };
    await mockThreadsAndStream(page, state);

    await page.goto("/chat");
    await page.getByRole("button", { name: "Leave policy" }).click();
    await expect(page.getByText(FULL_ANSWER)).toBeVisible();

    const availableToggle = page.getByRole("button", { name: /handbook\.pdf/ });
    await availableToggle.click();
    await expect(
      page.getByText("Employees are entitled to 25 days of annual leave each year."),
    ).toBeVisible();
    await expect(availableToggle).toContainText("p. 4");

    // Collapsing hides the excerpt again without touching the answer text.
    await availableToggle.click();
    await expect(
      page.getByText("Employees are entitled to 25 days of annual leave each year."),
    ).toHaveCount(0);
    await expect(page.getByText(FULL_ANSWER)).toBeVisible();

    const deletedToggle = page.getByRole("button", { name: /old-policy\.pdf/ });
    await deletedToggle.click();
    await expect(page.getByText(/no longer in the library/i)).toBeVisible();
  });
});

test.describe("AC-037: reopening an incomplete answer", () => {
  test("shows the did-not-complete indication and allows asking again", async ({ page }) => {
    const state = {
      threads: [{ id: THREAD_ID, title: "Leave policy", last_active_at: new Date().toISOString() }],
      detail: threadDetail([
        {
          id: "msg-user-1",
          role: "user",
          content: "How many leave days do employees get?",
          status: "complete",
          citations: [],
        },
        {
          id: MESSAGE_ID,
          role: "assistant",
          content: "Employees get ",
          status: "incomplete",
          citations: [],
        },
      ]),
      streamBody: sseBody(["Employees get 25 days of annual leave each year."], []),
      messagesCalls: 0,
    };
    await mockThreadsAndStream(page, state);

    await page.goto("/chat");
    await page.getByRole("button", { name: "Leave policy" }).click();

    await expect(page.getByText("This answer did not finish.")).toBeVisible();
    const askAgain = page.getByRole("button", { name: "Ask again" });
    await expect(askAgain).toBeVisible();

    // Once the retry succeeds, update what GET /threads/{id} would now
    // return so the post-send refresh reflects a completed answer.
    state.detail = threadDetail([
      {
        id: "msg-user-1",
        role: "user",
        content: "How many leave days do employees get?",
        status: "complete",
        citations: [],
      },
      {
        id: MESSAGE_ID,
        role: "assistant",
        content: "Employees get 25 days of annual leave each year.",
        status: "complete",
        citations: [],
      },
    ]);

    await askAgain.click();

    await expect(page.getByText("Employees get 25 days of annual leave each year.")).toBeVisible();
    expect(state.messagesCalls).toBe(1);
  });
});
