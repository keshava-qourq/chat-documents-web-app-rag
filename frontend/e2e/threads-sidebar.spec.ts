import { expect, test, type Page } from "@playwright/test";

// US-013..017 / AC-041..054: the shared threads sidebar. Every network call
// in this spec is intercepted with `page.route` against a small in-memory
// fixture -- nothing here reaches the real backend, a live Gemini call, or
// MinIO, and there is no wall-clock wait anywhere in it.

const THREAD_ID = "22222222-2222-2222-2222-222222222222";

function makeThreadFixture() {
  return {
    id: THREAD_ID,
    title: "Berlin office holidays",
    last_active_at: new Date().toISOString(),
  };
}

function makeThreadDetail(title: string) {
  return {
    id: THREAD_ID,
    title,
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
        citations: [
          {
            id: "cit-1",
            document_name: "handbook.pdf",
            source_location: "p. 12",
            excerpt: "Berlin office closes for the Christmas holidays from 24 Dec to 2 Jan.",
          },
        ],
      },
    ],
  };
}

async function mockThreadsApi(
  page: Page,
  state: {
    threads: Array<{ id: string; title: string; last_active_at: string }>;
    deleted: boolean;
    renameCalls: number;
    deleteCalls: number;
  },
) {
  await page.route("**/threads", async (route) => {
    const method = route.request().method();
    if (method === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(state.deleted ? [] : state.threads),
      });
      return;
    }
    await route.continue();
  });

  await page.route(`**/threads/${THREAD_ID}`, async (route) => {
    const method = route.request().method();
    if (method === "GET") {
      if (state.deleted) {
        await route.fulfill({ status: 404, contentType: "application/json", body: "{}" });
        return;
      }
      const current = state.threads.find((t) => t.id === THREAD_ID)!;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(makeThreadDetail(current.title)),
      });
      return;
    }
    if (method === "PATCH") {
      state.renameCalls += 1;
      const payload = route.request().postDataJSON() as { title: string };
      const title = (payload.title ?? "").trim();
      if (!title) {
        await route.fulfill({
          status: 422,
          contentType: "application/json",
          body: JSON.stringify({ detail: "Title must not be empty" }),
        });
        return;
      }
      const current = state.threads.find((t) => t.id === THREAD_ID)!;
      current.title = title;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ id: THREAD_ID, title }),
      });
      return;
    }
    if (method === "DELETE") {
      state.deleteCalls += 1;
      state.deleted = true;
      state.threads = state.threads.filter((t) => t.id !== THREAD_ID);
      await route.fulfill({ status: 204, body: "" });
      return;
    }
    await route.continue();
  });
}

test.describe("AC-043: empty sidebar state", () => {
  test("shows an empty-state message and a working new-conversation action", async ({ page }) => {
    const state = { threads: [], deleted: true, renameCalls: 0, deleteCalls: 0 };
    await mockThreadsApi(page, state);

    await page.goto("/chat");

    await expect(page.getByText("No conversations yet")).toBeVisible();
    await page.getByRole("button", { name: "New conversation" }).first().click();

    await expect(page.getByRole("heading", { name: "Start a new conversation" })).toBeVisible();
    await expect(page.getByPlaceholder("Ask a question about the documents…")).toBeVisible();
  });
});

test.describe("AC-045: opening an existing thread", () => {
  test("shows its history and citations", async ({ page }) => {
    const state = {
      threads: [makeThreadFixture()],
      deleted: false,
      renameCalls: 0,
      deleteCalls: 0,
    };
    await mockThreadsApi(page, state);

    await page.goto("/chat");

    await page.getByRole("button", { name: "Berlin office holidays" }).click();

    await expect(
      page.getByText("When does the Berlin office close for the Christmas holidays?"),
    ).toBeVisible();
    await expect(
      page.getByText("The Berlin office is closed from 24 December through 2 January."),
    ).toBeVisible();
    await expect(page.getByText("handbook.pdf")).toBeVisible();
    await expect(page.getByText(/Berlin office closes for the Christmas holidays/)).toBeVisible();
  });
});

test.describe("AC-051 / AC-052: renaming a conversation", () => {
  test("updates the sidebar title, and an empty rename is rejected", async ({ page }) => {
    const state = {
      threads: [makeThreadFixture()],
      deleted: false,
      renameCalls: 0,
      deleteCalls: 0,
    };
    await mockThreadsApi(page, state);

    await page.goto("/chat");
    await expect(page.getByRole("button", { name: "Berlin office holidays" })).toBeVisible();

    await page.getByLabel("Rename Berlin office holidays").click();
    const titleInput = page.getByLabel("Conversation title");
    await titleInput.fill("Holiday closures policy");
    await page.getByLabel("Save title").click();

    await expect(page.getByRole("button", { name: "Holiday closures policy" })).toBeVisible();
    expect(state.renameCalls).toBe(1);

    await page.getByLabel("Rename Holiday closures policy").click();
    await page.getByLabel("Conversation title").fill("   ");
    await page.getByLabel("Save title").click();

    await expect(page.getByText(/title can't be empty/i)).toBeVisible();
    // The rejected rename never reached the sidebar, and the previous title stands.
    await expect(page.getByRole("button", { name: "Holiday closures policy" })).toBeVisible();
  });
});

test.describe("AC-053: deleting a conversation", () => {
  test("with confirmation removes it from the sidebar", async ({ page }) => {
    const state = {
      threads: [makeThreadFixture()],
      deleted: false,
      renameCalls: 0,
      deleteCalls: 0,
    };
    await mockThreadsApi(page, state);

    await page.goto("/chat");
    await expect(page.getByRole("button", { name: "Berlin office holidays" })).toBeVisible();

    await page.getByLabel("Delete Berlin office holidays").click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();
    await expect(dialog.getByText(/permanent/i)).toBeVisible();
    await dialog.getByRole("button", { name: /delete permanently/i }).click();

    await expect(page.getByRole("dialog")).toBeHidden();
    await expect(page.getByRole("button", { name: "Berlin office holidays" })).toHaveCount(0);
    await expect(page.getByText("No conversations yet")).toBeVisible();
    expect(state.deleteCalls).toBe(1);
  });
});

test.describe("AC-054: deleting the open thread", () => {
  test("returns the chat area to the empty state", async ({ page }) => {
    const state = {
      threads: [makeThreadFixture()],
      deleted: false,
      renameCalls: 0,
      deleteCalls: 0,
    };
    await mockThreadsApi(page, state);

    await page.goto("/chat");
    await page.getByRole("button", { name: "Berlin office holidays" }).click();
    await expect(
      page.getByText("When does the Berlin office close for the Christmas holidays?"),
    ).toBeVisible();

    await page.getByLabel("Delete Berlin office holidays").click();
    await page
      .getByRole("dialog")
      .getByRole("button", { name: /delete permanently/i })
      .click();

    await expect(page.getByRole("heading", { name: "Start a new conversation" })).toBeVisible();
    await expect(
      page.getByText("When does the Berlin office close for the Christmas holidays?"),
    ).toHaveCount(0);
  });
});
