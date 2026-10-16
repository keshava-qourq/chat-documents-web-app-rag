import { expect, test } from "@playwright/test";

// The backend contract itself, driven through Playwright's `request` API
// against the running FastAPI service (the same one `playwright.config.ts`
// boots for every spec in this directory) rather than through the browser --
// status codes, response shapes, and the error cases a person never sees on
// screen but a client still depends on. Every other spec in this directory
// drives the UI and intercepts the network with `page.route`, so none of
// them ever actually calls the real backend; this file is what closes that
// gap for the parts of the api_spec that are pure API guarantees.
//
// Nothing here uploads a file that would actually reach storage, and
// nothing here asks a question against a library that has a 'ready'
// document in it -- both would require MinIO and Gemini to be configured,
// which this environment does not guarantee. Every request below either
// gets rejected before either service is touched, or exercises a thread/
// message path that `app.services.request_answer` itself never calls
// Gemini for when the shared library is empty.

const API_BASE_URL = process.env.E2E_API_BASE_URL ?? "http://127.0.0.1:8000";

test.describe("GET /documents -- shared library listing", () => {
  test("responds 200 with an array, and each item (if any) has the documented shape", async ({
    request,
  }) => {
    const response = await request.get(`${API_BASE_URL}/documents`);

    expect(response.status()).toBe(200);
    const body = await response.json();
    expect(Array.isArray(body)).toBe(true);
    for (const item of body) {
      expect(item).toHaveProperty("id");
      expect(item).toHaveProperty("file_name");
      expect(item).toHaveProperty("size_bytes");
      expect(item).toHaveProperty("uploaded_at");
      expect(item).toHaveProperty("status");
      expect(item).toHaveProperty("failure_reason");
      expect(item).toHaveProperty("chunk_count");
    }
  });
});

test.describe("POST /documents -- validation rejects before storage or indexing", () => {
  test("rejects an unsupported file type with the documented accepted/rejected shape", async ({
    request,
  }) => {
    const response = await request.post(`${API_BASE_URL}/documents`, {
      multipart: {
        files: {
          name: "budget.xlsx",
          mimeType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
          buffer: Buffer.from("fake spreadsheet bytes"),
        },
      },
    });

    expect(response.status()).toBe(200);
    const body = await response.json();
    expect(body.accepted).toEqual([]);
    expect(body.rejected).toHaveLength(1);
    expect(body.rejected[0].file_name).toBe("budget.xlsx");
    expect(typeof body.rejected[0].reason).toBe("string");
    expect(body.rejected[0].reason.length).toBeGreaterThan(0);
  });
});

test.describe("GET /documents/{id}/status -- unknown id", () => {
  test("responds 404 for a document id that does not exist", async ({ request }) => {
    const response = await request.get(
      `${API_BASE_URL}/documents/00000000-0000-0000-0000-000000000000/status`,
    );
    expect(response.status()).toBe(404);
  });
});

test.describe("DELETE /documents/{id} -- unknown id", () => {
  test("responds 404 for a document id that does not exist", async ({ request }) => {
    const response = await request.delete(
      `${API_BASE_URL}/documents/00000000-0000-0000-0000-000000000001`,
    );
    expect(response.status()).toBe(404);
  });
});

test.describe("GET /threads -- shared thread listing", () => {
  test("responds 200 with an array, most recently active first", async ({ request }) => {
    const response = await request.get(`${API_BASE_URL}/threads`);
    expect(response.status()).toBe(200);
    const body = await response.json();
    expect(Array.isArray(body)).toBe(true);
    for (const item of body) {
      expect(item).toHaveProperty("id");
      expect(item).toHaveProperty("title");
      expect(item).toHaveProperty("last_active_at");
    }
    const timestamps = body.map((t: { last_active_at: string }) =>
      new Date(t.last_active_at).getTime(),
    );
    const sorted = [...timestamps].sort((a, b) => b - a);
    expect(timestamps).toEqual(sorted);
  });
});

test.describe("POST /threads -- create an empty thread", () => {
  test("responds 200 with id, title and created_at, and the thread is then listed and loadable", async ({
    request,
  }) => {
    const created = await request.post(`${API_BASE_URL}/threads`);
    expect(created.status()).toBe(200);
    const createdBody = await created.json();
    expect(createdBody).toHaveProperty("id");
    expect(createdBody).toHaveProperty("title");
    expect(createdBody).toHaveProperty("created_at");
    expect(createdBody.title).toBe("New conversation");

    const detail = await request.get(`${API_BASE_URL}/threads/${createdBody.id}`);
    expect(detail.status()).toBe(200);
    const detailBody = await detail.json();
    expect(detailBody.id).toBe(createdBody.id);
    expect(detailBody.title).toBe("New conversation");
    expect(detailBody.messages).toEqual([]);
  });
});

test.describe("GET /threads/{id} -- unknown id", () => {
  test("responds 404 for a thread id that does not exist", async ({ request }) => {
    const response = await request.get(
      `${API_BASE_URL}/threads/00000000-0000-0000-0000-000000000002`,
    );
    expect(response.status()).toBe(404);
  });
});

test.describe("PATCH /threads/{id} -- rename", () => {
  test("renames with a 200 {id,title} shape, and rejects an empty title with 422", async ({
    request,
  }) => {
    const created = await request.post(`${API_BASE_URL}/threads`);
    const { id } = await created.json();

    const renamed = await request.patch(`${API_BASE_URL}/threads/${id}`, {
      data: { title: "Office relocation FAQ" },
    });
    expect(renamed.status()).toBe(200);
    const renamedBody = await renamed.json();
    expect(renamedBody).toEqual({ id, title: "Office relocation FAQ" });

    const blanked = await request.patch(`${API_BASE_URL}/threads/${id}`, {
      data: { title: "   " },
    });
    expect(blanked.status()).toBe(422);

    // The rejected rename must not have overwritten the title.
    const detail = await request.get(`${API_BASE_URL}/threads/${id}`);
    expect((await detail.json()).title).toBe("Office relocation FAQ");
  });

  test("renaming an unknown thread id responds 404", async ({ request }) => {
    const response = await request.patch(
      `${API_BASE_URL}/threads/00000000-0000-0000-0000-000000000003`,
      { data: { title: "Anything" } },
    );
    expect(response.status()).toBe(404);
  });
});

test.describe("DELETE /threads/{id} -- permanent deletion", () => {
  test("responds 204, and the thread is unreachable and unlisted afterwards", async ({
    request,
  }) => {
    const created = await request.post(`${API_BASE_URL}/threads`);
    const { id } = await created.json();

    const deleted = await request.delete(`${API_BASE_URL}/threads/${id}`);
    expect(deleted.status()).toBe(204);
    const deletedBody = await deleted.text();
    expect(deletedBody).toBe("");

    const afterGet = await request.get(`${API_BASE_URL}/threads/${id}`);
    expect(afterGet.status()).toBe(404);

    const listed = await request.get(`${API_BASE_URL}/threads`);
    const ids = (await listed.json()).map((t: { id: string }) => t.id);
    expect(ids).not.toContain(id);

    // Deleting the same id again is a 404, not a 500 or a second 204.
    const secondDelete = await request.delete(`${API_BASE_URL}/threads/${id}`);
    expect(secondDelete.status()).toBe(404);
  });
});

test.describe("POST /threads/{id}/messages -- the chat contract", () => {
  test("streams text/event-stream and ends with a persisted 'not found' reply when the shared library has no ready document", async ({
    request,
  }) => {
    const created = await request.post(`${API_BASE_URL}/threads`);
    const { id } = await created.json();

    const response = await request.post(`${API_BASE_URL}/threads/${id}/messages`, {
      data: { question: "Is there anything indexed yet?" },
    });

    expect(response.status()).toBe(200);
    expect(response.headers()["content-type"]).toContain("text/event-stream");
    const body = await response.text();
    expect(body).toContain("event: token");
    expect(body).toContain("event: final");
    // No 'ready' document exists anywhere in the shared library for this
    // backend, so the canned, Gemini-free reply applies and the assistant
    // turn is never persisted (see `app.services.request_answer`) --
    // `message_id` reports that explicitly as `null` rather than an id.
    expect(body).toMatch(/"message_id":\s*null/);

    // The user's own question is still persisted even though no answer was.
    const detail = await request.get(`${API_BASE_URL}/threads/${id}`);
    const messages = (await detail.json()).messages;
    expect(messages[0]).toMatchObject({
      role: "user",
      content: "Is there anything indexed yet?",
      status: "complete",
    });
  });

  test("posting to an unknown thread id responds 404", async ({ request }) => {
    const response = await request.post(
      `${API_BASE_URL}/threads/00000000-0000-0000-0000-000000000004/messages`,
      { data: { question: "Anything?" } },
    );
    expect(response.status()).toBe(404);
  });
});
