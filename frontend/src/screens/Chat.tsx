import React from "react";
import { Link, useSearchParams } from "react-router-dom";
import ReactMarkdown from "react-markdown";

import * as UI from "@/lib/ui";
import { Icons } from "@/lib/icons";
import { brand } from "@/lib/brand";
import {
  listThreads,
  createThread,
  getThread,
  renameThread,
  deleteThread,
  postMessage,
  isNoDocumentsIndexedError,
  type CitationRecord,
  type ThreadSummary,
  type ThreadDetail,
  type MessageRecord,
} from "@/lib/api";

const { Button, Input, Textarea, Empty } = UI;
const { Plus, Edit, Trash, Check, X, ArrowRight, AlertCircle, ChevronDown } = Icons;

const STARTERS = [
  "What's the per-head limit for client dinners?",
  "Which laptops are approved for contractors?",
  "How much parental leave top-up do Dutch staff get?",
  "When does the Berlin office close over Christmas?",
];

function cx(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}

/**
 * One entry per distinct source (file name + page/section), in first-seen
 * order -- the same source chunked multiple times must not list twice
 * (AC-029, AC-030).
 */
function dedupeCitations(citations: CitationRecord[]): CitationRecord[] {
  const seen = new Set<string>();
  const result: CitationRecord[] = [];
  for (const c of citations) {
    const key = `${c.document_name} ${c.source_location ?? ""}`;
    if (seen.has(key)) continue;
    seen.add(key);
    result.push(c);
  }
  return result;
}

/**
 * A single citation, collapsed by default. Expanding it reveals the exact
 * retrieved excerpt alongside its file name and page/section (AC-032).
 * Collapsing hides the excerpt again without touching the answer text
 * (AC-033); each citation tracks its own expanded state independently.
 * When the source document has since been removed from the library, the
 * expanded area says so instead of showing an empty or erroring excerpt
 * (AC-034).
 */
function CitationItem({ citation }: { citation: CitationRecord }) {
  const [expanded, setExpanded] = React.useState(false);
  const panelId = `citation-panel-${citation.id}`;
  const available = citation.document_available !== false;

  return (
    <li>
      <button
        type="button"
        aria-expanded={expanded}
        aria-controls={panelId}
        className="flex w-full items-center justify-between gap-2 rounded px-1 py-1 text-left font-semibold text-slate-700 hover:bg-slate-50"
        onClick={() => setExpanded((prev) => !prev)}
      >
        <span>
          {citation.document_name}
          {citation.source_location ? ` · ${citation.source_location}` : ""}
        </span>
        <ChevronDown
          size={12}
          className={cx("shrink-0 transition-transform", expanded && "rotate-180")}
          aria-hidden="true"
        />
      </button>
      {expanded && (
        <div id={panelId} className="px-1 pb-2 pt-0.5 text-slate-600">
          {available ? (
            <p>{citation.excerpt}</p>
          ) : (
            <p className="italic text-slate-500">
              This source document is no longer in the library.
            </p>
          )}
        </div>
      )}
    </li>
  );
}

export default function Screen() {
  const [searchParams, setSearchParams] = useSearchParams();
  const activeId = searchParams.get("thread");

  const [threads, setThreads] = React.useState<ThreadSummary[]>([]);
  const [threadsLoading, setThreadsLoading] = React.useState(true);
  const [threadsError, setThreadsError] = React.useState<string | null>(null);

  const [activeThread, setActiveThread] = React.useState<ThreadDetail | null>(null);
  const [threadLoading, setThreadLoading] = React.useState(false);
  const [loadError, setLoadError] = React.useState<string | null>(null);

  const [composer, setComposer] = React.useState("");
  const [sending, setSending] = React.useState(false);
  const [sendError, setSendError] = React.useState<string | null>(null);
  const [noDocumentsIndexed, setNoDocumentsIndexed] = React.useState(false);

  const [renamingId, setRenamingId] = React.useState<string | null>(null);
  const [renameValue, setRenameValue] = React.useState("");
  const [renameError, setRenameError] = React.useState<string | null>(null);
  const [renameSaving, setRenameSaving] = React.useState(false);

  const [confirmDeleteId, setConfirmDeleteId] = React.useState<string | null>(null);
  const [deleting, setDeleting] = React.useState(false);

  const sendingRef = React.useRef(false);

  const fetchThreads = React.useCallback(async () => {
    try {
      const data = await listThreads();
      const sorted = [...data].sort(
        (a, b) => new Date(b.last_active_at).getTime() - new Date(a.last_active_at).getTime(),
      );
      setThreads(sorted);
      setThreadsError(null);
    } catch {
      setThreadsError("Could not load conversations. Check your connection and try again.");
    } finally {
      setThreadsLoading(false);
    }
  }, []);

  React.useEffect(() => {
    fetchThreads();
  }, [fetchThreads]);

  const loadThread = React.useCallback(async (id: string) => {
    setThreadLoading(true);
    setLoadError(null);
    try {
      const detail = await getThread(id);
      setActiveThread(detail);
    } catch {
      setLoadError("Couldn't load this conversation. Try again.");
    } finally {
      setThreadLoading(false);
    }
  }, []);

  React.useEffect(() => {
    if (!activeId) {
      setActiveThread(null);
      setLoadError(null);
      return;
    }
    if (sendingRef.current) return;
    loadThread(activeId);
  }, [activeId, loadThread]);

  const openThread = (id: string) => {
    setRenamingId(null);
    setSendError(null);
    setNoDocumentsIndexed(false);
    setSearchParams({ thread: id });
  };

  const newConversation = () => {
    setRenamingId(null);
    setLoadError(null);
    setSendError(null);
    setNoDocumentsIndexed(false);
    setActiveThread(null);
    searchParams.delete("thread");
    setSearchParams(searchParams);
  };

  const handleSend = async (questionOverride?: string) => {
    const question = (questionOverride ?? composer).trim();
    if (!question || sending) return;

    sendingRef.current = true;
    setSending(true);
    setSendError(null);
    setNoDocumentsIndexed(false);
    const optimisticId = `pending-${Date.now()}`;
    const streamingId = `streaming-${Date.now()}`;
    const optimisticMessage: MessageRecord = {
      id: optimisticId,
      role: "user",
      content: question,
      status: "complete",
      citations: [],
    };
    // A placeholder assistant message that fills in token by token as the
    // stream arrives (AC-035), replacing the old "Sending…"-then-everything
    // behaviour. It is discarded in favour of the persisted thread on
    // success, or removed entirely if the stream fails.
    const streamingMessage: MessageRecord = {
      id: streamingId,
      role: "assistant",
      content: "",
      status: "streaming",
      citations: [],
    };
    setActiveThread((prev) => ({
      id: prev?.id ?? activeId ?? "",
      title: prev?.title ?? "New conversation",
      messages: [...(prev?.messages ?? []), optimisticMessage, streamingMessage],
    }));
    setComposer("");

    try {
      let threadId = activeId;
      if (!threadId) {
        const created = await createThread();
        threadId = created.id;
      }
      await postMessage(threadId, question, (text) => {
        setActiveThread((prev) =>
          prev
            ? {
                ...prev,
                messages: prev.messages.map((m) =>
                  m.id === streamingId ? { ...m, content: m.content + text } : m,
                ),
              }
            : prev,
        );
      });
      // The 'final' event only carries the message id and citations; the
      // persisted content/status for both turns comes from the thread
      // detail, which also keeps the sidebar and this view in sync
      // (AC-036).
      const detail = await getThread(threadId);
      setActiveThread(detail);
      if (threadId !== activeId) {
        setSearchParams({ thread: threadId });
      }
      await fetchThreads();
    } catch (err) {
      if (isNoDocumentsIndexedError(err)) {
        // Keep the question visible; show the "no documents" message in
        // place of an answer instead of treating this as a send failure.
        setNoDocumentsIndexed(true);
      } else {
        // Covers both a rejected send and a connection dropped mid-stream:
        // discard the optimistic turn, restore the question into the
        // composer, and leave the composer enabled (AC-037).
        setActiveThread((prev) =>
          prev
            ? {
                ...prev,
                messages: prev.messages.filter(
                  (m) => m.id !== optimisticId && m.id !== streamingId,
                ),
              }
            : prev,
        );
        setComposer(question);
        setSendError("Couldn't send that question. Try again.");
      }
    } finally {
      setSending(false);
      sendingRef.current = false;
    }
  };

  const startRename = (thread: ThreadSummary) => {
    setRenamingId(thread.id);
    setRenameValue(thread.title);
    setRenameError(null);
  };

  const cancelRename = () => {
    setRenamingId(null);
    setRenameValue("");
    setRenameError(null);
  };

  const saveRename = async (id: string) => {
    const trimmed = renameValue.trim();
    if (!trimmed) {
      setRenameError("Title can't be empty.");
      return;
    }
    setRenameSaving(true);
    try {
      const result = await renameThread(id, trimmed);
      setRenamingId(null);
      setRenameError(null);
      await fetchThreads();
      setActiveThread((prev) => (prev && prev.id === id ? { ...prev, title: result.title } : prev));
    } catch {
      setRenameError("Couldn't save that title. Try again.");
    } finally {
      setRenameSaving(false);
    }
  };

  const performDelete = async () => {
    const id = confirmDeleteId;
    if (!id) return;
    setDeleting(true);
    try {
      await deleteThread(id);
      setThreads((prev) => prev.filter((t) => t.id !== id));
      setConfirmDeleteId(null);
      if (activeId === id) {
        newConversation();
      }
    } catch {
      setThreadsError("Couldn't delete that conversation. Try again.");
    } finally {
      setDeleting(false);
    }
  };

  const confirmDeleteThread = threads.find((t) => t.id === confirmDeleteId) ?? null;

  return (
    <div
      className="mx-auto flex h-full w-full max-w-6xl flex-col gap-4 px-4 py-6 sm:px-6 lg:flex-row"
      style={{ fontFamily: brand.fontBody }}
    >
      {/* Sidebar: shared conversation list */}
      <aside
        className="flex w-full shrink-0 flex-col rounded-[var(--brand-radius,0.5rem)] border border-slate-200 bg-white lg:w-72"
        aria-label="Conversations"
      >
        <div className="flex items-center justify-between border-b border-slate-100 p-3">
          <h2 className="text-sm font-semibold text-slate-900">Conversations</h2>
          <Button size="sm" variant="secondary" onClick={newConversation}>
            <Plus size={14} aria-hidden="true" />
            New conversation
          </Button>
        </div>

        {threadsLoading ? (
          <p className="p-4 text-sm text-slate-500">Loading conversations…</p>
        ) : threadsError ? (
          <div role="alert" className="p-4 text-sm">
            <p className="text-red-700">{threadsError}</p>
            <button
              type="button"
              className="mt-2 font-semibold text-slate-700 underline underline-offset-2"
              onClick={fetchThreads}
            >
              Retry
            </button>
          </div>
        ) : threads.length === 0 ? (
          <div className="p-4">
            <Empty
              title="No conversations yet"
              description="Start the first conversation with the shared document library."
              action={
                <Button size="sm" onClick={newConversation}>
                  New conversation
                </Button>
              }
            />
          </div>
        ) : (
          <ul className="flex-1 overflow-y-auto p-2" aria-label="Conversation list">
            {threads.map((t) => {
              const isActive = t.id === activeId;
              const isRenaming = renamingId === t.id;
              return (
                <li key={t.id} className="group">
                  {isRenaming ? (
                    <form
                      className="flex items-center gap-1 p-1"
                      onSubmit={(e) => {
                        e.preventDefault();
                        saveRename(t.id);
                      }}
                    >
                      <Input
                        autoFocus
                        aria-label="Conversation title"
                        value={renameValue}
                        disabled={renameSaving}
                        onChange={(e) => {
                          setRenameValue(e.target.value);
                          setRenameError(null);
                        }}
                        className="h-8 text-sm"
                      />
                      <button
                        type="submit"
                        aria-label="Save title"
                        className="shrink-0 p-1 text-slate-600"
                        disabled={renameSaving}
                      >
                        <Check size={14} aria-hidden="true" />
                      </button>
                      <button
                        type="button"
                        aria-label="Cancel rename"
                        className="shrink-0 p-1 text-slate-600"
                        onClick={cancelRename}
                        disabled={renameSaving}
                      >
                        <X size={14} aria-hidden="true" />
                      </button>
                    </form>
                  ) : (
                    <div
                      className={cx(
                        "flex items-center gap-1 rounded-[var(--brand-radius,0.5rem)] px-2 py-2",
                        isActive && "bg-slate-100",
                      )}
                    >
                      <button
                        type="button"
                        className="min-w-0 flex-1 truncate text-left text-sm text-slate-800"
                        title={t.title}
                        aria-current={isActive ? "true" : undefined}
                        onClick={() => openThread(t.id)}
                      >
                        {t.title}
                      </button>
                      <button
                        type="button"
                        aria-label={`Rename ${t.title}`}
                        className="shrink-0 rounded p-1 text-slate-500 hover:bg-slate-200"
                        onClick={() => startRename(t)}
                      >
                        <Edit size={14} aria-hidden="true" />
                      </button>
                      <button
                        type="button"
                        aria-label={`Delete ${t.title}`}
                        className="shrink-0 rounded p-1 text-slate-500 hover:bg-slate-200"
                        onClick={() => setConfirmDeleteId(t.id)}
                      >
                        <Trash size={14} aria-hidden="true" />
                      </button>
                    </div>
                  )}
                  {isRenaming && renameError && (
                    <p className="px-2 pb-1 text-xs text-red-600">{renameError}</p>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </aside>

      {/* Main chat area */}
      <section className="flex min-w-0 flex-1 flex-col rounded-[var(--brand-radius,0.5rem)] border border-slate-200 bg-white">
        <div className="flex-1 overflow-y-auto p-4">
          {!activeId && !activeThread ? (
            <div className="flex flex-col items-center justify-center gap-4 py-12 text-center">
              <h2 className="text-lg font-semibold text-slate-900">Start a new conversation</h2>
              <p className="max-w-md text-sm text-slate-500">
                Ask anything about the shared document library. Your question and its answer will be
                visible to everyone with the link.
              </p>
              <div className="grid w-full max-w-xl gap-2 sm:grid-cols-2">
                {STARTERS.map((s) => (
                  <button
                    key={s}
                    type="button"
                    className="rounded-[var(--brand-radius,0.5rem)] border border-slate-200 p-3 text-left text-sm text-slate-700 hover:bg-slate-50"
                    onClick={() => handleSend(s)}
                    disabled={sending}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          ) : threadLoading ? (
            <p className="text-sm text-slate-500">Loading conversation…</p>
          ) : loadError ? (
            <div role="alert" className="text-sm">
              <p className="text-red-700">{loadError}</p>
              <button
                type="button"
                className="mt-2 font-semibold text-slate-700 underline underline-offset-2"
                onClick={() => activeId && loadThread(activeId)}
              >
                Retry
              </button>
            </div>
          ) : activeThread ? (
            <>
              <ul className="space-y-6">
                {activeThread.messages.map((m, index) => {
                  const sources = m.role === "assistant" ? dedupeCitations(m.citations ?? []) : [];
                  const isIncomplete = m.role === "assistant" && m.status === "incomplete";
                  return (
                    <li
                      key={m.id}
                      className={m.role === "user" ? "flex justify-end" : "flex justify-start"}
                    >
                      <div
                        className={cx(
                          "max-w-[85%] rounded-[var(--brand-radius,0.5rem)] px-4 py-3 text-sm",
                          m.role === "user"
                            ? "bg-[var(--brand-primary,#C2410C)] text-white"
                            : "bg-slate-100 text-slate-800",
                        )}
                      >
                        {isIncomplete ? (
                          <div>
                            <p className="flex items-start gap-2 italic text-slate-600">
                              <AlertCircle
                                size={16}
                                className="mt-0.5 shrink-0"
                                aria-hidden="true"
                              />
                              This answer did not finish.
                            </p>
                            <button
                              type="button"
                              className="mt-2 font-semibold text-slate-700 underline underline-offset-2"
                              onClick={() => {
                                const previousUser = [...activeThread.messages.slice(0, index)]
                                  .reverse()
                                  .find((candidate) => candidate.role === "user");
                                if (previousUser) handleSend(previousUser.content);
                              }}
                              disabled={sending}
                            >
                              Ask again
                            </button>
                          </div>
                        ) : (
                          <div className="prose prose-sm max-w-none">
                            <ReactMarkdown>{m.content}</ReactMarkdown>
                          </div>
                        )}
                        {sources.length > 0 && (
                          <div className="mt-3 border-t border-slate-200 pt-2">
                            <p className="text-xs font-semibold text-slate-700">Sources</p>
                            <ul className="mt-1 space-y-1 text-xs text-slate-600">
                              {sources.map((c) => (
                                <CitationItem key={c.id} citation={c} />
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    </li>
                  );
                })}
              </ul>

              {noDocumentsIndexed && (
                <div
                  role="status"
                  className="mt-6 flex items-start gap-2 rounded-[var(--brand-radius,0.5rem)] border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900"
                >
                  <AlertCircle size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
                  <p>
                    There are no documents indexed yet, so there is nothing to search. Upload a
                    document on the{" "}
                    <Link to="/documents" className="font-semibold underline underline-offset-2">
                      Documents screen
                    </Link>{" "}
                    and ask again.
                  </p>
                </div>
              )}

              {sendError && (
                <div
                  role="alert"
                  className="mt-6 flex items-start gap-2 rounded-[var(--brand-radius,0.5rem)] border border-red-200 bg-red-50 p-4 text-sm text-red-700"
                >
                  <AlertCircle size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
                  <div>
                    <p>{sendError}</p>
                    <button
                      type="button"
                      className="mt-1 font-semibold underline underline-offset-2"
                      onClick={() => handleSend(composer)}
                    >
                      Retry
                    </button>
                  </div>
                </div>
              )}
            </>
          ) : null}
        </div>

        <form
          className="flex items-end gap-2 border-t border-slate-100 p-3"
          onSubmit={(e) => {
            e.preventDefault();
            handleSend();
          }}
        >
          <label className="sr-only" htmlFor="chat-composer">
            Ask a question
          </label>
          <Textarea
            id="chat-composer"
            value={composer}
            placeholder="Ask a question about the documents…"
            disabled={sending}
            onChange={(e) => setComposer(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            className="min-h-[44px] flex-1"
          />
          <Button type="submit" disabled={sending || !composer.trim()}>
            {sending ? "Sending…" : "Send"}
            <ArrowRight size={16} aria-hidden="true" />
          </Button>
        </form>
      </section>

      {/* Delete confirmation */}
      {confirmDeleteThread && (
        <div
          className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 p-4 sm:items-center"
          onMouseDown={(e) => {
            if (e.target === e.currentTarget) setConfirmDeleteId(null);
          }}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-thread-title"
            aria-describedby="delete-thread-desc"
            className="w-full max-w-md rounded-[var(--brand-radius,0.5rem)] border border-slate-200 bg-white p-6"
          >
            <h2 id="delete-thread-title" className="text-lg font-semibold text-slate-900">
              Delete this conversation?
            </h2>
            <p className="mt-2 text-sm font-medium text-slate-800">{confirmDeleteThread.title}</p>
            <p
              id="delete-thread-desc"
              className="mt-3 flex items-start gap-2 text-sm text-slate-600"
            >
              <AlertCircle size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
              This is permanent. There is no undo, and no copy is kept.
            </p>
            <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
              <button
                type="button"
                className="rounded-[var(--brand-radius,0.5rem)] border border-slate-200 px-4 py-2.5 text-sm font-semibold text-slate-700 disabled:cursor-not-allowed disabled:opacity-60"
                disabled={deleting}
                onClick={() => setConfirmDeleteId(null)}
              >
                Keep it
              </button>
              <button
                type="button"
                className="rounded-[var(--brand-radius,0.5rem)] bg-red-600 px-4 py-2.5 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
                disabled={deleting}
                onClick={performDelete}
              >
                {deleting ? "Deleting…" : "Delete permanently"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
