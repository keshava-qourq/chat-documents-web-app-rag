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
} from "@/lib/api";
import Screen from "./Chat";

vi.mock("@/lib/api", () => ({
  listThreads: vi.fn(),
  createThread: vi.fn(),
  getThread: vi.fn(),
  renameThread: vi.fn(),
  deleteThread: vi.fn(),
  postMessage: vi.fn(),
}));

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
    await waitFor(() => expect(screen.queryByText(/loading conversations/i)).not.toBeInTheDocument());
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

  it("loads a thread via GET /threads/{id} and renders questions, answers and citations in order", async () => {
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
    expect(screen.getByText(/Handbook\.pdf/)).toBeInTheDocument();
    expect(screen.getByText("Top-up is 100%.")).toBeInTheDocument();
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
    await waitFor(() => expect(mockedPostMessage).toHaveBeenCalledWith("t-new", "Hello?"));
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

    await waitFor(() => expect(mockedPostMessage).toHaveBeenCalledWith("t-1", "And desktops?"));
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
      messages: [{ id: "m-1", role: "user", content: "Still here?", status: "complete", citations: [] }],
    });

    renderScreen(["/chat?thread=t-1"]);

    await waitFor(() => expect(mockedGetThread).toHaveBeenCalledWith("t-1"));
    expect(await screen.findByText("Still here?")).toBeInTheDocument();
    expect(localStorage.length).toBe(0);
  });
});
