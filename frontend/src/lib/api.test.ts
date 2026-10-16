// Direct coverage for `app/lib/api.ts` itself -- the one seam between the two
// halves of this sprint that no other test exercises directly. Every screen
// test (`Chat.test.tsx`, `Documents.test.tsx`) mocks this whole module with
// `vi.mock("@/lib/api")`, so the real `apiFetch`/`postMessage` implementation
// -- the SSE framing, the buffering across chunked reads, and the typed
// error it raises for each failure shape the backend's contract promises --
// is only ever exercised indirectly, through the Playwright specs that mock
// the network instead. This file calls the real functions against a faked
// `fetch`, so a change that breaks the SSE parser or the error mapping fails
// here, fast, without a browser.
import { afterEach, describe, expect, it, vi } from "vitest";

import { apiFetch, ApiError, isNoDocumentsIndexedError, postMessage } from "./api";

/** A `Response`-like object whose body streams `chunks` one `read()` at a
 * time -- including a chunk boundary landing mid-frame, mid-JSON, which is
 * exactly what a real chunked HTTP response can do to the SSE parser's
 * buffering. */
function makeStreamResponse(
  chunks: string[],
  init: { status?: number; ok?: boolean; detail?: string } = {},
) {
  let index = 0;
  const encoder = new TextEncoder();
  return {
    ok: init.ok ?? true,
    status: init.status ?? 200,
    json: async () => ({ detail: init.detail ?? "" }),
    body: {
      getReader: () => ({
        read: async () => {
          if (index >= chunks.length) return { done: true, value: undefined };
          const value = encoder.encode(chunks[index]);
          index += 1;
          return { done: false, value };
        },
      }),
    },
  } as unknown as Response;
}

describe("postMessage — SSE stream parsing against the real backend contract", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("calls onToken for each token event, in order, and resolves with the final event's payload", async () => {
    const response = makeStreamResponse([
      'event: token\ndata: {"text":"Hello "}\n\n',
      'event: token\ndata: {"text":"world"}\n\n',
      'event: final\ndata: {"message_id":"m-1","citations":[{"id":"c-1","document_name":"a.pdf","source_location":null,"excerpt":"x"}]}\n\n',
    ]);
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => response),
    );

    const received: string[] = [];
    const result = await postMessage("t-1", "How many days?", (text) => received.push(text));

    expect(received).toEqual(["Hello ", "world"]);
    expect(result.message_id).toBe("m-1");
    expect(result.citations).toHaveLength(1);
    expect(result.citations[0].document_name).toBe("a.pdf");
  });

  it("reassembles an SSE frame split mid-JSON across two chunked reads", async () => {
    const response = makeStreamResponse([
      'event: token\ndata: {"te',
      'xt":"Hi"}\n\n',
      'event: final\ndata: {"message_id":"m-2","citations":[]}\n\n',
    ]);
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => response),
    );

    const received: string[] = [];
    const result = await postMessage("t-1", "question", (text) => received.push(text));

    expect(received).toEqual(["Hi"]);
    expect(result.message_id).toBe("m-2");
  });

  it("rejects with an ApiError isNoDocumentsIndexedError recognises when the final event reports message_id: null", async () => {
    const response = makeStreamResponse([
      'event: token\ndata: {"text":"No documents yet."}\n\n',
      'event: final\ndata: {"message_id":null,"citations":[]}\n\n',
    ]);
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => response),
    );

    await expect(postMessage("t-1", "question")).rejects.toSatisfy(
      (err: unknown) => err instanceof ApiError && isNoDocumentsIndexedError(err),
    );
  });

  it("rejects with the backend's own detail text when the stream sends an error event", async () => {
    const response = makeStreamResponse([
      'event: token\ndata: {"text":"partial"}\n\n',
      'event: error\ndata: {"detail":"The answer generation service is unavailable."}\n\n',
    ]);
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => response),
    );

    await expect(postMessage("t-1", "question")).rejects.toThrow(
      "The answer generation service is unavailable.",
    );
  });

  it("rejects when the connection drops before a final event ever arrives", async () => {
    const response = makeStreamResponse(['event: token\ndata: {"text":"partial"}\n\n']);
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => response),
    );

    await expect(postMessage("t-1", "question")).rejects.toThrow(/dropped/i);
  });

  it("rejects with an ApiError carrying the status and detail for a non-2xx response (e.g. rate limited)", async () => {
    const response = makeStreamResponse([], {
      ok: false,
      status: 429,
      detail: "Too many requests, try again shortly.",
    });
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => response),
    );

    await expect(postMessage("t-1", "question")).rejects.toMatchObject({
      status: 429,
      detail: "Too many requests, try again shortly.",
    });
  });

  // AC-067/AC-068 integration: `routers.threads.post_message`'s pre-flight
  // check raises `HTTPException(503, detail={"code": "gemini_not_configured",
  // "message": "..."})` -- an *object*-shaped `detail`, unlike every other
  // endpoint's plain string `detail`. `postMessage`'s error branch only ever
  // reads a string out of `body.detail`, so this must not throw while
  // parsing the body (e.g. on `JSON.stringify` of something unexpected) and
  // must not leak the raw object through `.detail` -- it falls back to the
  // same empty string any other unrecognised body shape gets, which is what
  // every caller already knows how to treat as a generic, retryable failure.
  it("does not crash and falls back to an empty detail when a 503 response's detail is the gemini-not-configured object shape", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: false,
        status: 503,
        json: async () => ({
          detail: {
            code: "gemini_not_configured",
            message: "GEMINI_API_KEY is not set. Set it in the server's environment.",
          },
        }),
      })),
    );

    await expect(postMessage("t-1", "question")).rejects.toMatchObject({
      status: 503,
      detail: "",
    });
  });
});

describe("apiFetch — the JSON request helper every other endpoint function is built on", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("parses a successful JSON response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        status: 200,
        json: async () => ({ hello: "world" }),
      })),
    );

    await expect(apiFetch<{ hello: string }>("/anything")).resolves.toEqual({ hello: "world" });
  });

  it("resolves to undefined for a 204 No Content response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({ ok: true, status: 204, json: async () => ({}) })),
    );

    await expect(apiFetch("/documents/some-id")).resolves.toBeUndefined();
  });

  it("throws an ApiError carrying the status and the backend's detail text on failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: false,
        status: 404,
        json: async () => ({ detail: "Thread not found" }),
      })),
    );

    await expect(apiFetch("/threads/unknown")).rejects.toMatchObject({
      status: 404,
      detail: "Thread not found",
    });
  });

  it("falls back to an empty detail when the error response body is not JSON", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: false,
        status: 500,
        json: async () => {
          throw new SyntaxError("not json");
        },
      })),
    );

    await expect(apiFetch("/threads/unknown")).rejects.toMatchObject({
      status: 500,
      detail: "",
    });
  });

  it("falls back to an empty detail (not the raw object) when a response's detail is object-shaped", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: false,
        status: 503,
        json: async () => ({ detail: { code: "gemini_not_configured", message: "unset" } }),
      })),
    );

    await expect(apiFetch("/threads/unknown")).rejects.toMatchObject({
      status: 503,
      detail: "",
    });
  });
});
