// Coverage for US-022-1: message bubble alignment. Chat.test.tsx already
// covers streaming, citations, and error behaviour end-to-end; this file
// only asserts the alignment/test-hook contract added for this ticket, so
// it does not duplicate that coverage.
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { listThreads, createThread, getThread, postMessage } from "@/lib/api";
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
const mockedPostMessage = vi.mocked(postMessage);

function renderScreen(initialEntries: string[] = ["/chat"]) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <Screen />
    </MemoryRouter>,
  );
}

describe("Chat message bubble alignment", () => {
  beforeEach(() => {
    mockedListThreads.mockReset();
    mockedCreateThread.mockReset();
    mockedGetThread.mockReset();
    mockedPostMessage.mockReset();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("[AC-071] renders user bubbles right-aligned and assistant bubbles left-aligned, each with a stable test hook", async () => {
    mockedListThreads.mockResolvedValue([
      { id: "t-1", title: "Thread", last_active_at: "2026-10-16T10:00:00Z" },
    ]);
    mockedGetThread.mockResolvedValue({
      id: "t-1",
      title: "Thread",
      messages: [
        { id: "m-1", role: "user", content: "A question", status: "complete", citations: [] },
        { id: "m-2", role: "assistant", content: "An answer", status: "complete", citations: [] },
      ],
    });

    const user = userEvent.setup();
    renderScreen();

    await screen.findByText("Thread");
    await user.click(screen.getByRole("button", { name: "Thread" }));
    await screen.findByText("A question");

    const bubbles = screen.getAllByTestId("message-bubble");
    expect(bubbles).toHaveLength(2);

    const userBubble = bubbles.find((b) => b.getAttribute("data-role") === "user")!;
    const assistantBubble = bubbles.find((b) => b.getAttribute("data-role") === "assistant")!;

    expect(userBubble.parentElement).toHaveClass("justify-end");
    expect(assistantBubble.parentElement).toHaveClass("justify-start");
  });

  it("[AC-072] keeps the streaming bubble left-aligned as it grows token by token", async () => {
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

    const assistantBubbleBefore = screen
      .getAllByTestId("message-bubble")
      .find((b) => b.getAttribute("data-role") === "assistant")!;
    expect(assistantBubbleBefore.parentElement).toHaveClass("justify-start");

    onTokenCallback?.("partial text");
    await screen.findByText("partial text");

    const assistantBubbleAfter = screen
      .getAllByTestId("message-bubble")
      .find((b) => b.getAttribute("data-role") === "assistant")!;
    expect(assistantBubbleAfter.parentElement).toHaveClass("justify-start");

    resolvePost({ message_id: "m-1", citations: [] });
  });

  it("[AC-073] wraps a long answer and long citation text inside the bubble's max-width without widening it", async () => {
    const longWord = "a".repeat(200);
    mockedListThreads.mockResolvedValue([
      { id: "t-1", title: "Long thread", last_active_at: "2026-10-16T10:00:00Z" },
    ]);
    mockedGetThread.mockResolvedValue({
      id: "t-1",
      title: "Long thread",
      messages: [
        {
          id: "m-2",
          role: "assistant",
          content: `See https://example.com/${longWord} for details.`,
          status: "complete",
          citations: [
            {
              id: "c-1",
              document_name: `${longWord}.pdf`,
              source_location: "page 1",
              excerpt: longWord,
              document_available: true,
            },
          ],
        },
      ],
    });

    const user = userEvent.setup();
    renderScreen();

    await screen.findByText("Long thread");
    await user.click(screen.getByRole("button", { name: "Long thread" }));

    const bubble = await screen.findByTestId("message-bubble");
    expect(bubble).toHaveClass("break-words");
    expect(bubble).toHaveClass("max-w-[85%]");
    expect(bubble).toHaveClass("overflow-hidden");
  });

  it("[AC-075] renders a reloaded thread's full history with the same alignment as a newly sent message", async () => {
    mockedListThreads.mockResolvedValue([
      { id: "t-1", title: "History", last_active_at: "2026-10-16T10:00:00Z" },
    ]);
    mockedGetThread.mockResolvedValue({
      id: "t-1",
      title: "History",
      messages: [
        { id: "m-1", role: "user", content: "First", status: "complete", citations: [] },
        { id: "m-2", role: "assistant", content: "Reply one", status: "complete", citations: [] },
        { id: "m-3", role: "user", content: "Second", status: "complete", citations: [] },
        { id: "m-4", role: "assistant", content: "Reply two", status: "complete", citations: [] },
      ],
    });

    renderScreen(["/chat?thread=t-1"]);

    await screen.findByText("Reply two");
    const rows = screen.getAllByTestId("message-row");
    expect(rows).toHaveLength(4);
    expect(rows[0]).toHaveClass("justify-end");
    expect(rows[1]).toHaveClass("justify-start");
    expect(rows[2]).toHaveClass("justify-end");
    expect(rows[3]).toHaveClass("justify-start");
  });
});
