import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { listDocuments, uploadDocuments, deleteDocument } from "@/lib/api";
import Screen from "./Documents";

vi.mock("@/lib/api", () => ({
  listDocuments: vi.fn(),
  uploadDocuments: vi.fn(),
  deleteDocument: vi.fn(),
  getDocumentStatus: vi.fn(),
}));

const mockedList = vi.mocked(listDocuments);
const mockedUpload = vi.mocked(uploadDocuments);
const mockedDelete = vi.mocked(deleteDocument);

function renderScreen() {
  return render(
    <MemoryRouter>
      <Screen />
    </MemoryRouter>,
  );
}

describe("Documents screen — indexing progress and failures", () => {
  beforeEach(() => {
    mockedList.mockReset();
    mockedUpload.mockReset();
    mockedDelete.mockReset();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders a determinate progress bar from the server progress value with no sample data", async () => {
    mockedList.mockResolvedValue([
      {
        id: "doc-1",
        file_name: "handbook.pdf",
        size_bytes: 1024,
        uploaded_at: new Date().toISOString(),
        status: "processing",
        progress: 42,
        failure_reason: null,
        chunk_count: 0,
      },
    ]);

    renderScreen();

    await waitFor(() => expect(mockedList).toHaveBeenCalledTimes(1));

    const bar = await screen.findByRole("progressbar", { name: /handbook\.pdf/i });
    expect(bar).toHaveAttribute("aria-valuenow", "42");
    expect(bar).toHaveAttribute("aria-valuemin", "0");
    expect(bar).toHaveAttribute("aria-valuemax", "100");
    expect(screen.getByText(/42%/)).toBeInTheDocument();
  });

  it("polls while a document is processing, updates aria-valuenow, and stops once terminal", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });

    mockedList
      .mockResolvedValueOnce([
        {
          id: "doc-1",
          file_name: "handbook.pdf",
          size_bytes: 1024,
          uploaded_at: new Date().toISOString(),
          status: "processing",
          progress: 10,
          failure_reason: null,
          chunk_count: 0,
        },
      ])
      .mockResolvedValueOnce([
        {
          id: "doc-1",
          file_name: "handbook.pdf",
          size_bytes: 1024,
          uploaded_at: new Date().toISOString(),
          status: "processing",
          progress: 60,
          failure_reason: null,
          chunk_count: 0,
        },
      ])
      .mockResolvedValue([
        {
          id: "doc-1",
          file_name: "handbook.pdf",
          size_bytes: 1024,
          uploaded_at: new Date().toISOString(),
          status: "ready",
          progress: 100,
          failure_reason: null,
          chunk_count: 8,
        },
      ]);

    renderScreen();

    await vi.waitFor(() => expect(mockedList).toHaveBeenCalledTimes(1));
    let bar = await screen.findByRole("progressbar");
    expect(bar).toHaveAttribute("aria-valuenow", "10");

    await vi.advanceTimersByTimeAsync(4000);
    await vi.waitFor(() => expect(mockedList).toHaveBeenCalledTimes(2));
    bar = await screen.findByRole("progressbar");
    expect(bar).toHaveAttribute("aria-valuenow", "60");

    await vi.advanceTimersByTimeAsync(4000);
    await vi.waitFor(() => expect(mockedList).toHaveBeenCalledTimes(3));
    await vi.waitFor(() => expect(screen.queryByRole("progressbar")).not.toBeInTheDocument());

    const callsAfterTerminal = mockedList.mock.calls.length;
    await vi.advanceTimersByTimeAsync(10000);
    expect(mockedList.mock.calls.length).toBe(callsAfterTerminal);
  });

  it("shows the server-supplied failure reason verbatim and no chunk count", async () => {
    mockedList.mockResolvedValue([
      {
        id: "doc-2",
        file_name: "contract.pdf",
        size_bytes: 2048,
        uploaded_at: new Date().toISOString(),
        status: "failed",
        progress: 0,
        failure_reason: "The embedding model returned a 503 after three retries.",
        chunk_count: 0,
      },
    ]);

    renderScreen();

    expect(
      await screen.findByText("The embedding model returned a 503 after three retries."),
    ).toBeInTheDocument();
    expect(screen.queryByText(/chunks indexed/)).not.toBeInTheDocument();
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
  });

  it("renders a scanned-PDF failure reason the same way, with no chunk count", async () => {
    mockedList.mockResolvedValue([
      {
        id: "doc-3",
        file_name: "scanned-invoice.pdf",
        size_bytes: 3000,
        uploaded_at: new Date().toISOString(),
        status: "failed",
        progress: 0,
        failure_reason: "This PDF appears to be scanned images with no extractable text.",
        chunk_count: 0,
      },
    ]);

    renderScreen();

    expect(
      await screen.findByText("This PDF appears to be scanned images with no extractable text."),
    ).toBeInTheDocument();
    expect(screen.queryByText(/chunks indexed/)).not.toBeInTheDocument();
  });

  it("surfaces upload rejections, including library-is-full, as error notices with the server's reason text", async () => {
    mockedList.mockResolvedValue([]);
    mockedUpload.mockResolvedValue({
      accepted: [],
      rejected: [
        {
          file_name: "overflow.pdf",
          reason: "The library is full: delete a document before uploading a new one.",
        },
      ],
    });

    const user = userEvent.setup();
    renderScreen();

    await waitFor(() => expect(mockedList).toHaveBeenCalled());

    const input = document.getElementById("document-files") as HTMLInputElement;
    const file = new File(["content"], "overflow.pdf", { type: "application/pdf" });
    await user.upload(input, file);

    const notice = await screen.findByText(/overflow\.pdf wasn't uploaded/i);
    expect(notice).toBeInTheDocument();
    expect(
      screen.getByText("The library is full: delete a document before uploading a new one."),
    ).toBeInTheDocument();
  });

  it("handles a mixed batch response: the accepted file joins the board while the cap-rejected file only shows a notice", async () => {
    // A batch can straddle the cap: earlier files in the same upload call
    // land inside the limit and get accepted, a later one pushes the
    // library over it and comes back rejected in the very same response.
    // Both outcomes have to be reflected at once, not one clobbering the
    // other.
    mockedList.mockResolvedValue([]);
    mockedUpload.mockResolvedValue({
      accepted: [
        {
          id: "doc-9",
          file_name: "first.pdf",
          size_bytes: 1000,
          mime_type: "application/pdf",
          status: "processing",
          uploaded_at: new Date().toISOString(),
        },
      ],
      rejected: [
        {
          file_name: "second.pdf",
          reason: "The library is full (2 document limit). Delete an existing document first.",
        },
      ],
    });

    const user = userEvent.setup();
    renderScreen();

    await waitFor(() => expect(mockedList).toHaveBeenCalled());

    const input = document.getElementById("document-files") as HTMLInputElement;
    const files = [
      new File(["a"], "first.pdf", { type: "application/pdf" }),
      new File(["b"], "second.pdf", { type: "application/pdf" }),
    ];
    await user.upload(input, files);

    expect(await screen.findByText("first.pdf")).toBeInTheDocument();
    expect(await screen.findByText(/second\.pdf wasn't uploaded/i)).toBeInTheDocument();
    expect(
      screen.getByText("The library is full (2 document limit). Delete an existing document first."),
    ).toBeInTheDocument();
    expect(screen.queryByText("second.pdf")).not.toBeInTheDocument();
  });

  it("deletes a document via the real API and removes it from the board", async () => {
    mockedList.mockResolvedValue([
      {
        id: "doc-4",
        file_name: "policy.docx",
        size_bytes: 500,
        uploaded_at: new Date().toISOString(),
        status: "ready",
        progress: 100,
        failure_reason: null,
        chunk_count: 5,
      },
    ]);
    mockedDelete.mockResolvedValue(undefined);

    const user = userEvent.setup();
    renderScreen();

    await screen.findByText("policy.docx");
    await user.click(screen.getByRole("button", { name: /delete policy\.docx/i }));

    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: /delete permanently/i }));

    await waitFor(() => expect(mockedDelete).toHaveBeenCalledWith("doc-4"));
    await waitFor(() => expect(screen.queryByText("policy.docx")).not.toBeInTheDocument());
  });

  it("states the deletion is permanent with no undo, requires no sign-in, and shows no 'deleted by' attribution", async () => {
    mockedList.mockResolvedValue([
      {
        id: "doc-5",
        file_name: "confidential.pdf",
        size_bytes: 777,
        uploaded_at: new Date().toISOString(),
        status: "ready",
        progress: 100,
        failure_reason: null,
        chunk_count: 3,
      },
    ]);
    mockedDelete.mockResolvedValue(undefined);

    const user = userEvent.setup();
    renderScreen();

    await screen.findByText("confidential.pdf");
    expect(screen.queryByText(/sign in/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/log in/i)).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /delete confidential\.pdf/i }));

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(/no undo/i)).toBeInTheDocument();
    expect(within(dialog).queryByText(/deleted by/i)).not.toBeInTheDocument();
    expect(within(dialog).queryByText(/sign in/i)).not.toBeInTheDocument();

    await user.click(within(dialog).getByRole("button", { name: /delete permanently/i }));

    await waitFor(() => expect(mockedDelete).toHaveBeenCalledWith("doc-5"));
    await waitFor(() => expect(screen.queryByText("confidential.pdf")).not.toBeInTheDocument());
    expect(screen.queryByText(/deleted by/i)).not.toBeInTheDocument();
  });

  it("cancelling the confirmation keeps the document and issues no DELETE request", async () => {
    mockedList.mockResolvedValue([
      {
        id: "doc-6",
        file_name: "keep-me.pdf",
        size_bytes: 400,
        uploaded_at: new Date().toISOString(),
        status: "ready",
        progress: 100,
        failure_reason: null,
        chunk_count: 2,
      },
    ]);

    const user = userEvent.setup();
    renderScreen();

    await screen.findByText("keep-me.pdf");
    await user.click(screen.getByRole("button", { name: /delete keep-me\.pdf/i }));

    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: /keep it/i }));

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(screen.getByText("keep-me.pdf")).toBeInTheDocument();
    expect(mockedDelete).not.toHaveBeenCalled();
  });

  it("surfaces a non-blocking error when the DELETE request fails, leaving the document in place", async () => {
    mockedList.mockResolvedValue([
      {
        id: "doc-7",
        file_name: "stubborn.pdf",
        size_bytes: 900,
        uploaded_at: new Date().toISOString(),
        status: "ready",
        progress: 100,
        failure_reason: null,
        chunk_count: 1,
      },
    ]);
    mockedDelete.mockRejectedValue(new Error("DELETE /documents/doc-7 failed: 500"));

    const user = userEvent.setup();
    renderScreen();

    await screen.findByText("stubborn.pdf");
    await user.click(screen.getByRole("button", { name: /delete stubborn\.pdf/i }));

    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: /delete permanently/i }));

    await waitFor(() => expect(mockedDelete).toHaveBeenCalledWith("doc-7"));
    expect(await screen.findByText(/couldn't delete stubborn\.pdf/i)).toBeInTheDocument();
    expect(screen.getAllByText("stubborn.pdf").length).toBeGreaterThan(0);
  });

  it("allows deleting a document that is still processing, and its poller stops for that id once deleted", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });

    mockedList.mockResolvedValue([
      {
        id: "doc-8",
        file_name: "in-progress.pdf",
        size_bytes: 1200,
        uploaded_at: new Date().toISOString(),
        status: "processing",
        progress: 20,
        failure_reason: null,
        chunk_count: 0,
      },
    ]);
    mockedDelete.mockResolvedValue(undefined);

    const user = userEvent.setup();
    renderScreen();

    await vi.waitFor(() => expect(mockedList).toHaveBeenCalledTimes(1));
    await screen.findByText("in-progress.pdf");

    await user.click(screen.getByRole("button", { name: /delete in-progress\.pdf/i }));
    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: /delete permanently/i }));

    await vi.waitFor(() => expect(mockedDelete).toHaveBeenCalledWith("doc-8"));
    await vi.waitFor(() => expect(screen.queryByText("in-progress.pdf")).not.toBeInTheDocument());

    const callsAfterDelete = mockedList.mock.calls.length;
    await vi.advanceTimersByTimeAsync(10000);
    expect(mockedList.mock.calls.length).toBe(callsAfterDelete);
  });
});
