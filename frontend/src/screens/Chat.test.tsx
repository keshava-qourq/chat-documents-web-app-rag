import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { ThreadSummary } from "@/lib/api";
import {
  listThreads,
  createThread,
  getThread,
  renameThread,
  deleteThread,
  postMessage,
  ApiError,
  isNoDocumentsIndexedError,
} from "@/lib/api";
import Screen from "./Chat";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    listThreads: vi.fn(),
    createThread: vi.fn(),
    getThread: vi.fn(),
    renameThread: vi.fn(),
    deleteThread: vi.fn(),
    postMessage: vi.fn(),
  };
});

const mockedListThreads = vi.mocked(listThreads);
const mockedCreateThread = vi.mocked(createThread);
const mockedGetThread = vi.mocked(getThread);
const mockedRenameThread = vi.mocked(renameThread);
const mockedDeleteThread = vi.mocked(deleteThread);
const mockedPostMessage = vi.mocked(postMessage);

function renderScreen(initialEntries: string[] = ["/chat"]) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <Screen />
    </MemoryRouter>,
  );
}

describe("Chat screen — live threads API", () => {
  beforeEach(() => {
    mockedListThreads.mockReset();
    mockedCreateThread.mockReset();
    mockedGetThread.mockReset();
    mockedRenameThread.mockReset();
    mockedDeleteThread.mockReset();
    mockedPostMessage.mockReset();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders threads from GET /threads, most recently active first, each showing its title", async () => {
    mockedListThreads.mockResolvedValue([
      { id: "t-1", title: "Older thread", last_active_at: "2026-10-10T10:00:00Z" },
      { id: "t-2", title: "Newer thread", last_active_at: "2026-10-16T10:00:00Z" },
    ]);

    renderScreen();

    await waitFor(() => expect(mockedListThreads).toHaveBeenCalledTimes(1));
    const list = await screen.findByLabelText("Conversation list");
    const listItems = within(list).getAllByRole("listitem");
    expect(listItems[0]).toHaveTextContent("Newer thread");
    expect(listItems[1]).toHaveTextContent("Older thread");
    expect(within(list).getByRole("button", { name: "Newer thread" })).toBeInTheDocument();
    expect(within(list).getByRole("button", { name: "Older thread" })).toBeInTheDocument();
  });

  it("shows an empty state with a working new-conversation affordance when there are zero threads", async () => {
    mockedListThreads.mockResolvedValue([]);
    renderScreen();

    expect(await screen.findByText("No conversations yet")).toBeInTheDocument();
    const startButtons = screen.getAllByRole("button", { name: /new conversation/i });
    expect(startButtons.length).toBeGreaterThan(0);
    expect(screen.getByText(/start a new conversation/i)).toBeInTheDocument();
  });

  it("shows a loading state for the sidebar, then clears it once threads resolve", async () => {
    let resolveList: (value: ThreadSummary[]) => void = () => {};
    mockedListThreads.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveList = resolve;
        }),
    );
    renderScreen();
    expect(screen.getByText(/loading conversations/i)).toBeInTheDocument();
    resolveList([]);
    await waitFor(() =>
      expect(screen.queryByText(/loading conversations/i)).not.toBeInTheDocument(),
    );
  });

  it("surfaces a sidebar load error with a retry that succeeds", async () => {
    mockedListThreads.mockRejectedValueOnce(new Error("boom"));
    mockedListThreads.mockResolvedValue([]);

    const user = userEvent.setup();
    renderScreen();

    await screen.findByText(/could not load conversations/i);
    await user.click(screen.getByRole("button", { name: /retry/i }));

    await waitFor(() => expect(mockedListThreads).toHaveBeenCalledTimes(2));
    expect(await screen.findByText("No conversations yet")).toBeInTheDocument();
  });

  it("loads a thread via GET /threads/{id} and renders questions, answers and citations in order, with citations collapsed until expanded", async () => {
    mockedListThreads.mockResolvedValue([
      { id: "t-1", title: "Parental leave", last_active_at: "2026-10-16T10:00:00Z" },
    ]);
    mockedGetThread.mockResolvedValue({
      id: "t-1",
      title: "Parental leave",
      messages: [
        { id: "m-1", role: "user", content: "How much top-up?", status: "complete", citations: [] },
        {
          id: "m-2",
          role: "assistant",
          content: "Here is the answer.",
          status: "complete",
          citations: [
            {
              id: "c-1",
              document_name: "Handbook.pdf",
              source_location: "page 3",
              excerpt: "Top-up is 100%.",
              document_available: true,
            },
          ],
        },
      ],
    });

    const user = userEvent.setup();
    renderScreen();

    await screen.findByText("Parental leave");
    await user.click(screen.getByRole("button", { name: "Parental leave" }));

    await waitFor(() => expect(mockedGetThread).toHaveBeenCalledWith("t-1"));
    expect(await screen.findByText("How much top-up?")).toBeInTheDocument();
    expect(await screen.findByText("Here is the answer.")).toBeInTheDocument();

    const citationToggle = screen.getByRole("button", { name: /Handbook\.pdf/ });
    expect(citationToggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText("Top-up is 100%.")).not.toBeInTheDocument();

    await user.click(citationToggle);
    expect(citationToggle).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("Top-up is 100%.")).toBeInTheDocument();
    expect(screen.getByText("Here is the answer.")).toBeInTheDocument();

    await user.click(citationToggle);
    expect(citationToggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText("Top-up is 100%.")).not.toBeInTheDocument();
    expect(screen.getByText("Here is the answer.")).toBeInTheDocument();
  });

  it("expands a citation to show the excerpt via the keyboard", async () => {
    mockedListThreads.mockResolvedValue([
      { id: "t-1", title: "Keyboard thread", last_active_at: "2026-10-16T10:00:00Z" },
    ]);
    mockedGetThread.mockResolvedValue({
      id: "t-1",
      title: "Keyboard thread",
      messages: [
        {
          id: "m-2",
          role: "assistant",
          content: "Answer.",
          status: "complete",
          citations: [
            {
              id: "c-1",
              document_name: "Policy.pdf",
              source_location: "page 1",
              excerpt: "Keyboard-reachable excerpt.",
              document_available: true,
            },
          ],
        },
      ],
    });

    const user = userEvent.setup();
    renderScreen();

    await screen.findByText("Keyboard thread");
    await user.click(screen.getByRole("button", { name: "Keyboard thread" }));
    await screen.findByText("Answer.");

    const citationToggle = screen.getByRole("button", { name: /Policy\.pdf/ });
    citationToggle.focus();
    expect(citationToggle).toHaveFocus();
    await user.keyboard("{Enter}");

    expect(citationToggle).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("Keyboard-reachable excerpt.")).toBeInTheDocument();
  });

  it("states the source document is no longer in the library when document_available is false", async () => {
    mockedListThreads.mockResolvedValue([
      { id: "t-1", title: "Missing doc", last_active_at: "2026-10-16T10:00:00Z" },
    ]);
    mockedGetThread.mockResolvedValue({
      id: "t-1",
      title: "Missing doc",
      messages: [
        {
          id: "m-2",
          role: "assistant",
          content: "Answer here.",
          status: "complete",
          citations: [
            {
              id: "c-1",
              document_name: "Deleted.pdf",
              source_location: "page 9",
              excerpt: "",
              document_available: false,
            },
          ],
        },
      ],
    });

    const user = userEvent.setup();
    renderScreen();

    await screen.findByText("Missing doc");
    await user.click(screen.getByRole("button", { name: "Missing doc" }));
    await screen.findByText("Answer here.");

    const citationToggle = screen.getByRole("button", { name: /Deleted\.pdf/ });
    await user.click(citationToggle);

    expect(screen.getByText(/no longer in the library/i)).toBeInTheDocument();
  });

  it("shows a 'did not finish' note with a way to ask again for an incomplete assistant message, and keeps the composer usable", async () => {
    mockedListThreads.mockResolvedValue([
      { id: "t-1", title: "Unfinished", last_active_at: "2026-10-16T10:00:00Z" },
    ]);
    mockedGetThread.mockResolvedValue({
      id: "t-1",
      title: "Unfinished",
      messages: [
        { id: "m-1", role: "user", content: "What happened?", status: "complete", citations: [] },
        {
          id: "m-2",
          role: "assistant",
          content: "",
          status: "incomplete",
          citations: [],
        },
      ],
    });
    mockedPostMessage.mockResolvedValue({ message_id: "m-3", citations: [] });

    const user = userEvent.setup();
    renderScreen();

    await screen.findByText("Unfinished");
    await user.click(screen.getByRole("button", { name: "Unfinished" }));

    expect(await screen.findByText(/did not finish/i)).toBeInTheDocument();
    const composer = screen.getByLabelText(/ask a question/i) as HTMLTextAreaElement;
    expect(composer).not.toBeDisabled();

    mockedGetThread.mockResolvedValue({
      id: "t-1",
      title: "Unfinished",
      messages: [
        { id: "m-1", role: "user", content: "What happened?", status: "complete", citations: [] },
        {
          id: "m-2",
          role: "assistant",
          content: "",
          status: "incomplete",
          citations: [],
        },
        { id: "m-3", role: "assistant", content: "Now it finished.", status: "complete", citations: [] },
      ],
    });

    await user.click(screen.getByRole("button", { name: /ask again/i }));
    await waitFor(() => expect(mockedPostMessage).toHaveBeenCalledWith("t-1", "What happened?", expect.any(Function)));
    expect(await screen.findByText("Now it finished.")).toBeInTheDocument();
  });

  it("renders assistant text progressively as token events arrive, then settles on the final persisted message", async () => {
    mockedListThreads.mockResolvedValue([]);
    mockedCreateThread.mockResolvedValue({
      id: "t-new",
      title: "New conversation",
      created_at: "2026-10-16T10:00:00Z",
    });

    let onTokenCallback: ((text: string) => void) | undefined;
    let resolvePost: (value: { message_id: string; citations: never[] }) => void = () => {};
    mockedPostMessage.mockImplementation((_id, _question, onToken) => {
      onTokenCallback = onToken;
      return new Promise((resolve) => {
        resolvePost = resolve;
      });
    });

    const user = userEvent.setup();
    renderScreen();

    await screen.findByText("No conversations yet");
    const composer = screen.getByLabelText(/ask a question/i);
    await user.type(composer, "Stream this?");
    await user.click(screen.getByRole("button", { name: /^send/i }));

    await waitFor(() => expect(onTokenCallback).toBeDefined());

    onTokenCallback?.("Hello");
    expect(await screen.findByText("Hello")).toBeInTheDocument();

    onTokenCallback?.(" world");
    expect(await screen.findByText("Hello world")).toBeInTheDocument();

    mockedGetThread.mockResolvedValue({
      id: "t-new",
      title: "New conversation",
      messages: [
        { id: "m-1", role: "user", content: "Stream this?", status: "complete", citations: [] },
        {
          id: "m-2",
          role: "assistant",
          content: "Hello world, fully settled.",
          status: "complete",
          citations: [],
        },
      ],
    });
    resolvePost({ message_id: "m-2", citations: [] });

    expect(await screen.findByText("Hello world, fully settled.")).toBeInTheDocument();
    expect(screen.queryByText("Hello world")).not.toBeInTheDocument();
  });

  it("creates a new thread and posts the first message when sending from the empty composer state", async () => {
    mockedListThreads.mockResolvedValue([]);
    mockedCreateThread.mockResolvedValue({
      id: "t-new",
      title: "New conversation",
      created_at: "2026-10-16T10:00:00Z",
    });
    mockedPostMessage.mockResolvedValue({ message_id: "m-1", citations: [] });
    mockedGetThread.mockResolvedValue({
      id: "t-new",
      title: "New conversation",
      messages: [
        { id: "m-1", role: "user", content: "Hello?", status: "complete", citations: [] },
        { id: "m-2", role: "assistant", content: "Hi there.", status: "complete", citations: [] },
      ],
    });

    const user = userEvent.setup();
    renderScreen();

    await screen.findByText("No conversations yet");
    const composer = screen.getByLabelText(/ask a question/i);
    await user.type(composer, "Hello?");
    await user.click(screen.getByRole("button", { name: /^send/i }));

    await waitFor(() => expect(mockedCreateThread).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(mockedPostMessage).toHaveBeenCalledWith("t-new", "Hello?", expect.any(Function)));
    expect(await screen.findByText("Hi there.")).toBeInTheDocument();
  });

  it("posts to an existing thread id when sending a follow-up question in a thread started by someone else", async () => {
    mockedListThreads.mockResolvedValue([
      { id: "t-1", title: "Laptops", last_active_at: "2026-10-16T10:00:00Z" },
    ]);
    mockedGetThread.mockResolvedValue({
      id: "t-1",
      title: "Laptops",
      messages: [
        { id: "m-1", role: "user", content: "Which laptops?", status: "complete", citations: [] },
      ],
    });
    mockedPostMessage.mockResolvedValue({ message_id: "m-2", citations: [] });

    const user = userEvent.setup();
    renderScreen();

    await screen.findByText("Laptops");
    await user.click(screen.getByRole("button", { name: "Laptops" }));
    await screen.findByText("Which laptops?");

    mockedGetThread.mockResolvedValue({
      id: "t-1",
      title: "Laptops",
      messages: [
        { id: "m-1", role: "user", content: "Which laptops?", status: "complete", citations: [] },
        { id: "m-2", role: "user", content: "And desktops?", status: "complete", citations: [] },
      ],
    });

    const composer = screen.getByLabelText(/ask a question/i);
    await user.type(composer, "And desktops?");
    await user.click(screen.getByRole("button", { name: /^send/i }));

    await waitFor(() =>
      expect(mockedPostMessage).toHaveBeenCalledWith("t-1", "And desktops?", expect.any(Function)),
    );
    expect(mockedCreateThread).not.toHaveBeenCalled();
  });

  it("renames a thread inline and reflects the stored value after refetch", async () => {
    mockedListThreads
      .mockResolvedValueOnce([
        { id: "t-1", title: "Old title", last_active_at: "2026-10-16T10:00:00Z" },
      ])
      .mockResolvedValue([
        { id: "t-1", title: "New title", last_active_at: "2026-10-16T10:00:00Z" },
      ]);
    mockedRenameThread.mockResolvedValue({ id: "t-1", title: "New title" });

    const user = userEvent.setup();
    renderScreen();

    await screen.findByText("Old title");
    await user.click(screen.getByRole("button", { name: "Rename Old title" }));

    const input = screen.getByLabelText("Conversation title");
    await user.clear(input);
    await user.type(input, "New title");
    await user.click(screen.getByRole("button", { name: "Save title" }));

    await waitFor(() => expect(mockedRenameThread).toHaveBeenCalledWith("t-1", "New title"));
    expect(await screen.findByText("New title")).toBeInTheDocument();
  });

  it("blocks saving an empty title and keeps the previous title displayed", async () => {
    mockedListThreads.mockResolvedValue([
      { id: "t-1", title: "Keep me", last_active_at: "2026-10-16T10:00:00Z" },
    ]);

    const user = userEvent.setup();
    renderScreen();

    await screen.findByText("Keep me");
    await user.click(screen.getByRole("button", { name: "Rename Keep me" }));

    const input = screen.getByLabelText("Conversation title");
    await user.clear(input);
    await user.click(screen.getByRole("button", { name: "Save title" }));

    expect(mockedRenameThread).not.toHaveBeenCalled();
    expect(screen.getByText(/can't be empty/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Cancel rename" }));
    expect(screen.getByText("Keep me")).toBeInTheDocument();
  });

  it("shows a permanent-deletion warning, deletes via the API, and removes the thread from the sidebar", async () => {
    mockedListThreads.mockResolvedValue([
      { id: "t-1", title: "Doomed thread", last_active_at: "2026-10-16T10:00:00Z" },
    ]);
    mockedDeleteThread.mockResolvedValue(undefined);

    const user = userEvent.setup();
    renderScreen();

    await screen.findByText("Doomed thread");
    await user.click(screen.getByRole("button", { name: "Delete Doomed thread" }));

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(/is permanent/i)).toBeInTheDocument();
    expect(within(dialog).getByText(/no undo/i)).toBeInTheDocument();

    await user.click(within(dialog).getByRole("button", { name: /delete permanently/i }));

    await waitFor(() => expect(mockedDeleteThread).toHaveBeenCalledWith("t-1"));
    await waitFor(() => expect(screen.queryByText("Doomed thread")).not.toBeInTheDocument());
  });

  it("returns to the empty/new conversation state when deleting the currently open thread", async () => {
    mockedListThreads.mockResolvedValue([
      { id: "t-1", title: "Open thread", last_active_at: "2026-10-16T10:00:00Z" },
    ]);
    mockedGetThread.mockResolvedValue({
      id: "t-1",
      title: "Open thread",
      messages: [{ id: "m-1", role: "user", content: "Hi", status: "complete", citations: [] }],
    });
    mockedDeleteThread.mockResolvedValue(undefined);

    const user = userEvent.setup();
    renderScreen();

    await screen.findByText("Open thread");
    await user.click(screen.getByRole("button", { name: "Open thread" }));
    await screen.findByText("Hi");

    await user.click(screen.getByRole("button", { name: "Delete Open thread" }));
    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: /delete permanently/i }));

    await waitFor(() => expect(mockedDeleteThread).toHaveBeenCalledWith("t-1"));
    expect(await screen.findByText(/start a new conversation/i)).toBeInTheDocument();
    expect(screen.queryByText("Hi")).not.toBeInTheDocument();
  });

  it("restores the sidebar and the open thread from the server on reload, via the URL rather than localStorage", async () => {
    mockedListThreads.mockResolvedValue([
      { id: "t-1", title: "Persisted thread", last_active_at: "2026-10-16T10:00:00Z" },
    ]);
    mockedGetThread.mockResolvedValue({
      id: "t-1",
      title: "Persisted thread",
      messages: [
        { id: "m-1", role: "user", content: "Still here?", status: "complete", citations: [] },
      ],
    });

    renderScreen(["/chat?thread=t-1"]);

    await waitFor(() => expect(mockedGetThread).toHaveBeenCalledWith("t-1"));
    expect(await screen.findByText("Still here?")).toBeInTheDocument();
    expect(localStorage.length).toBe(0);
  });

  it("renders a Markdown answer and lists each distinct source once, even when the same source backs several chunks", async () => {
    mockedListThreads.mockResolvedValue([
      { id: "t-1", title: "Expenses", last_active_at: "2026-10-16T10:00:00Z" },
    ]);
    mockedGetThread.mockResolvedValue({
      id: "t-1",
      title: "Expenses",
      messages: [
        {
          id: "m-1",
          role: "user",
          content: "What's the limit?",
          status: "complete",
          citations: [],
        },
        {
          id: "m-2",
          role: "assistant",
          content: "The limit is **€50** per head.",
          status: "complete",
          citations: [
            {
              id: "c-1",
              document_name: "Policy.pdf",
              source_location: "page 2",
              excerpt: "Dinners are capped at €50 per head.",
            },
            {
              id: "c-2",
              document_name: "Policy.pdf",
              source_location: "page 2",
              excerpt: "Dinners are capped at €50 per head, repeated chunk.",
            },
            {
              id: "c-3",
              document_name: "Policy.pdf",
              source_location: "page 5",
              excerpt: "See appendix for exceptions.",
            },
          ],
        },
      ],
    });

    const user = userEvent.setup();
    renderScreen();

    await screen.findByText("Expenses");
    await user.click(screen.getByRole("button", { name: "Expenses" }));

    const strong = await screen.findByText("€50");
    expect(strong.tagName).toBe("STRONG");

    const sourcesHeading = screen.getByText("Sources");
    const sourcesBlock = sourcesHeading.parentElement as HTMLElement;
    expect(within(sourcesBlock).getAllByText(/Policy\.pdf/)).toHaveLength(2);
    expect(within(sourcesBlock).getByText(/page 2/)).toBeInTheDocument();
    expect(within(sourcesBlock).getByText(/page 5/)).toBeInTheDocument();
  });

  it("renders no sources block and no empty heading for an assistant answer with no citations", async () => {
    mockedListThreads.mockResolvedValue([
      { id: "t-1", title: "No sources", last_active_at: "2026-10-16T10:00:00Z" },
    ]);
    mockedGetThread.mockResolvedValue({
      id: "t-1",
      title: "No sources",
      messages: [
        { id: "m-1", role: "user", content: "General chat?", status: "complete", citations: [] },
        {
          id: "m-2",
          role: "assistant",
          content: "I don't have a grounded answer for that.",
          status: "complete",
          citations: [],
        },
      ],
    });

    const user = userEvent.setup();
    renderScreen();

    await screen.findByText("No sources");
    await user.click(screen.getByRole("button", { name: "No sources" }));

    await screen.findByText("I don't have a grounded answer for that.");
    expect(screen.queryByText("Sources")).not.toBeInTheDocument();
  });

  it("offers no control to limit the search to particular documents", async () => {
    mockedListThreads.mockResolvedValue([]);
    renderScreen();

    await screen.findByText("No conversations yet");
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
    expect(screen.queryByText(/limit.*document/i)).not.toBeInTheDocument();
  });

  it("shows a no-documents-indexed message with a working link to Documents instead of an answer", async () => {
    mockedListThreads.mockResolvedValue([]);
    mockedCreateThread.mockResolvedValue({
      id: "t-new",
      title: "New conversation",
      created_at: "2026-10-16T10:00:00Z",
    });
    mockedPostMessage.mockRejectedValue(
      new ApiError(422, "NO_DOCUMENTS_INDEXED", "POST failed: 422"),
    );

    const user = userEvent.setup();
    renderScreen();

    await screen.findByText("No conversations yet");
    const composer = screen.getByLabelText(/ask a question/i);
    await user.type(composer, "Anything in the library?");
    await user.click(screen.getByRole("button", { name: /^send/i }));

    expect(isNoDocumentsIndexedError(new ApiError(422, "NO_DOCUMENTS_INDEXED", "x"))).toBe(true);

    const notice = await screen.findByText(/no documents indexed yet/i);
    const container = notice.closest("div") as HTMLElement;
    const link = within(container).getByRole("link", { name: /documents screen/i });
    expect(link).toHaveAttribute("href", "/documents");
    expect(screen.getByText("Anything in the library?")).toBeInTheDocument();
  });

  it("shows an inline error, restores the failed question into the composer, and keeps earlier messages intact on a send failure", async () => {
    mockedListThreads.mockResolvedValue([
      { id: "t-1", title: "Laptops", last_active_at: "2026-10-16T10:00:00Z" },
    ]);
    mockedGetThread.mockResolvedValue({
      id: "t-1",
      title: "Laptops",
      messages: [
        { id: "m-1", role: "user", content: "Which laptops?", status: "complete", citations: [] },
        {
          id: "m-2",
          role: "assistant",
          content: "The Dell XPS.",
          status: "complete",
          citations: [],
        },
      ],
    });
    mockedPostMessage.mockRejectedValue(new Error("network down"));

    const user = userEvent.setup();
    renderScreen();

    await screen.findByText("Laptops");
    await user.click(screen.getByRole("button", { name: "Laptops" }));
    await screen.findByText("The Dell XPS.");

    const composer = screen.getByLabelText(/ask a question/i) as HTMLTextAreaElement;
    await user.type(composer, "And desktops?");
    await user.click(screen.getByRole("button", { name: /^send/i }));

    await screen.findByText(/couldn't send that question/i);
    expect(screen.getByText("Which laptops?")).toBeInTheDocument();
    expect(screen.getByText("The Dell XPS.")).toBeInTheDocument();
    expect(
      screen.queryByText(
        (_content, element) => element?.tagName === "P" && element.textContent === "And desktops?",
      ),
    ).not.toBeInTheDocument();
    expect(composer.value).toBe("And desktops?");
    expect(composer).not.toBeDisabled();

    mockedPostMessage.mockResolvedValue({ message_id: "m-3", citations: [] });
    mockedGetThread.mockResolvedValue({
      id: "t-1",
      title: "Laptops",
      messages: [
        { id: "m-1", role: "user", content: "Which laptops?", status: "complete", citations: [] },
        {
          id: "m-2",
          role: "assistant",
          content: "The Dell XPS.",
          status: "complete",
          citations: [],
        },
        { id: "m-3", role: "user", content: "And desktops?", status: "complete", citations: [] },
      ],
    });

    await user.click(screen.getByRole("button", { name: /retry/i }));
    await waitFor(() =>
      expect(mockedPostMessage).toHaveBeenCalledWith("t-1", "And desktops?", expect.any(Function)),
    );
    expect(await screen.findAllByText("And desktops?")).not.toHaveLength(0);
  });
});
