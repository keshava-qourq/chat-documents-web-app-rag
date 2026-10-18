import { expect, test } from "@playwright/test";

// US-010 / AC-015..018: permanent document deletion. Every network call in
// this spec is intercepted with `page.route` -- the confirmation dialog,
// the row removal and the "no DELETE on cancel" assertion are all pure
// frontend behaviour, so none of this ever reaches the real backend's
// storage layer, let alone a live MinIO or Gemini.

const DOCUMENT = {
  id: "11111111-1111-1111-1111-111111111111",
  file_name: "handbook.pdf",
  size_bytes: 10240,
  uploaded_at: new Date().toISOString(),
  status: "ready",
  progress: 100,
  failure_reason: null,
  chunk_count: 7,
};

async function mockDocumentsApi(
  page: import("@playwright/test").Page,
  deleteState: {
    deleted: boolean;
    deleteCalls: number;
  },
) {
  await page.route("**/documents", async (route) => {
    // The SPA's own route for this screen is also "/documents" -- a glob
    // like "**/documents" matches by URL suffix only, so without this
    // guard it would also intercept the page's own navigation request
    // (resourceType "document") and fulfil it with this JSON body instead
    // of letting the real app shell load, leaving every later locator in
    // this file waiting on a page that never mounted.
    if (route.request().resourceType() === "document") {
      await route.continue();
      return;
    }
    if (route.request().method() !== "GET") {
      await route.continue();
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(deleteState.deleted ? [] : [DOCUMENT]),
    });
  });

  await page.route(`**/documents/${DOCUMENT.id}`, async (route) => {
    if (route.request().method() !== "DELETE") {
      await route.continue();
      return;
    }
    deleteState.deleteCalls += 1;
    deleteState.deleted = true;
    await route.fulfill({ status: 204, body: "" });
  });
}

test.describe("AC-015..018: permanent document deletion", () => {
  test("the confirmation dialog warns deletion is permanent and cannot be undone", async ({
    page,
  }) => {
    const deleteState = { deleted: false, deleteCalls: 0 };
    await mockDocumentsApi(page, deleteState);

    await page.goto("/documents");
    await expect(page.getByText(DOCUMENT.file_name)).toBeVisible();

    await page
      .getByRole("button", { name: `Delete ${DOCUMENT.file_name} from the shared library` })
      .click();

    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();
    await expect(dialog.getByText(/no undo/i)).toBeVisible();
    await expect(dialog.getByRole("button", { name: /delete permanently/i })).toBeVisible();

    expect(deleteState.deleteCalls).toBe(0);
  });

  test("confirming the deletion removes the row from the library and issues one DELETE", async ({
    page,
  }) => {
    const deleteState = { deleted: false, deleteCalls: 0 };
    await mockDocumentsApi(page, deleteState);

    await page.goto("/documents");
    await expect(page.getByText(DOCUMENT.file_name)).toBeVisible();

    await page
      .getByRole("button", { name: `Delete ${DOCUMENT.file_name} from the shared library` })
      .click();
    const dialog = page.getByRole("dialog");
    await dialog.getByRole("button", { name: /delete permanently/i }).click();

    await expect(page.getByRole("dialog")).toBeHidden();
    // The document's own row title is an <h3> (role "heading"); a plain
    // text search for the file name also matches the success notice this
    // same deletion legitimately raises ("handbook.pdf deleted for
    // everyone"), so it never reaches a count of 0 even once the row is
    // gone. The heading is what actually identifies the row.
    await expect(page.getByRole("heading", { name: DOCUMENT.file_name })).toHaveCount(0);
    expect(deleteState.deleteCalls).toBe(1);
  });

  test("cancelling the confirmation leaves the document present and issues no DELETE", async ({
    page,
  }) => {
    const deleteState = { deleted: false, deleteCalls: 0 };
    await mockDocumentsApi(page, deleteState);

    await page.goto("/documents");
    await expect(page.getByText(DOCUMENT.file_name)).toBeVisible();

    await page
      .getByRole("button", { name: `Delete ${DOCUMENT.file_name} from the shared library` })
      .click();
    const dialog = page.getByRole("dialog");
    await dialog.getByRole("button", { name: /keep it/i }).click();

    await expect(page.getByRole("dialog")).toBeHidden();
    await expect(page.getByText(DOCUMENT.file_name)).toBeVisible();
    expect(deleteState.deleteCalls).toBe(0);
  });
});
