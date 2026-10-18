import { expect, test } from "@playwright/test";

// A criterion that spans both halves: the action happens in the UI, driven
// through the browser the way a person would, and the result is confirmed
// through the real backend's own API -- not through a mock this test set
// up itself. Unlike every other Chat spec in this directory (all of which
// intercept the network with `page.route`), nothing here is mocked: the
// page talks to the same real FastAPI backend `playwright.config.ts` boots
// for this whole suite, and the assertions read that backend's state back
// through Playwright's `request` API.
//
// The shared library has no `'ready'` document in this environment, so
// `app.services.request_answer` takes its own canned, Gemini-free path --
// nothing here ever calls Gemini, and nothing here uploads a file or
// otherwise touches MinIO.

const API_BASE_URL = process.env.E2E_API_BASE_URL ?? "http://127.0.0.1:8000";

/**
 * A short, unique-per-run question: unique enough to be unambiguous to find
 * among whatever other data the shared backend/database may already hold
 * from earlier runs or other specs, but kept comfortably under the 60
 * characters `app.services.derive_title` uses as its title budget -- past
 * that it truncates and appends an ellipsis, which would no longer match
 * the question verbatim.
 */
function uniqueQuestion(label: string): string {
  const suffix = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
  return `${label} ${suffix}?`;
}

test.describe("Asking a question in the UI persists the thread the real API reports", () => {
  test("a question sent from the empty composer creates a thread the backend can load independently", async ({
    page,
    request,
  }) => {
    const question = uniqueQuestion("Persistence check");

    await page.goto("/chat");
    await page.getByPlaceholder("Ask a question about the documents…").fill(question);
    await page.getByRole("button", { name: /^send$/i }).click();

    // The UI's own confirmation that the question was accepted: with no
    // ready documents anywhere in the shared library, the backend's canned
    // reply surfaces as this banner rather than a generated answer.
    await expect(page.getByText(/no documents indexed yet/i)).toBeVisible();
    // Scoped to the rendered message bubble (the only element with this
    // markup wrapping message text) rather than a bare `getByText`: the
    // thread the question creates is also persisted with this same text as
    // its auto-derived title (confirmed below via the API), so once the
    // sidebar refreshes it shows the identical text again as a button --
    // an unscoped locator would then match both and fail Playwright's
    // strict mode.
    await expect(page.locator("div.prose", { hasText: question })).toBeVisible();

    // Confirm the result through the real API, not through anything this
    // test told a mock to say: find the thread the UI must have created, by
    // the one piece of text that is unique to this run.
    const listed = await request.get(`${API_BASE_URL}/threads`);
    expect(listed.status()).toBe(200);
    const threads: Array<{ id: string; title: string }> = await listed.json();
    const match = threads.find((t) => t.title === question);
    expect(match, `no thread titled "${question}" was found via GET /threads`).toBeTruthy();

    const detail = await request.get(`${API_BASE_URL}/threads/${match!.id}`);
    expect(detail.status()).toBe(200);
    const detailBody = await detail.json();
    expect(detailBody.messages).toHaveLength(1);
    expect(detailBody.messages[0]).toMatchObject({
      role: "user",
      content: question,
      status: "complete",
    });
  });
});

test.describe("Renaming a conversation in the UI persists through the real PATCH endpoint", () => {
  test("the new title is readable from a fresh API call, not just from the page's own state", async ({
    page,
    request,
  }) => {
    const question = uniqueQuestion("Rename target check");
    const newTitle = `Renamed via UI ${Date.now()}`;

    await page.goto("/chat");
    await page.getByPlaceholder("Ask a question about the documents…").fill(question);
    await page.getByRole("button", { name: /^send$/i }).click();
    await expect(page.getByText(/no documents indexed yet/i)).toBeVisible();

    // The sidebar now shows the thread this question created; rename it
    // through the real UI control, not by calling the API directly.
    const sidebarEntry = page.getByRole("button", { name: question });
    await expect(sidebarEntry).toBeVisible();
    await page.getByLabel(`Rename ${question}`).click();
    const titleInput = page.getByLabel("Conversation title");
    await titleInput.fill(newTitle);
    await page.getByLabel("Save title").click();
    await expect(page.getByRole("button", { name: newTitle })).toBeVisible();

    // Confirm it really persisted server-side, through a request this page
    // never made and this test never mocked.
    const listed = await request.get(`${API_BASE_URL}/threads`);
    const threads: Array<{ id: string; title: string }> = await listed.json();
    const match = threads.find((t) => t.title === newTitle);
    expect(match, `no thread titled "${newTitle}" was found via GET /threads`).toBeTruthy();

    const detail = await request.get(`${API_BASE_URL}/threads/${match!.id}`);
    expect((await detail.json()).title).toBe(newTitle);
  });
});
