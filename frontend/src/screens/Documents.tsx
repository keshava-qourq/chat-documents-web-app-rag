// @ts-nocheck -- generated from the approved design under its JS runtime contract; not hand-written TypeScript.
/* eslint-disable @typescript-eslint/no-unused-vars */
import React from "react";

import * as UI from "@/lib/ui";
import { Icons } from "@/lib/icons";
import { brand } from "@/lib/brand";
import { useNavigate } from "@/lib/navigate";
import { listDocuments, uploadDocuments, deleteDocument } from "@/lib/api";

const { Button, Input, Label } = UI;
const {
  Plus,
  Search,
  Check,
  X,
  ChevronRight,
  Users,
  Settings,
  FileText,
  Clock,
  Trash,
  Filter,
  Upload,
  AlertCircle,
  CheckCircle,
} = Icons;

const MAX_FILE_BYTES = 25 * 1024 * 1024;
const ACCEPTED_EXTENSIONS = ["pdf", "docx", "txt", "md", "markdown"];
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const POLL_INTERVAL_MS = 4000;

const FILTERS = [
  { key: "all", label: "All" },
  { key: "ready", label: "Ready" },
  { key: "processing", label: "Indexing" },
  { key: "failed", label: "Failed" },
];

const toRgb = (hex) => {
  const h = String(hex || "#000000").replace("#", "");
  const full =
    h.length === 3
      ? h
          .split("")
          .map((c) => c + c)
          .join("")
      : h;
  return [
    parseInt(full.slice(0, 2), 16) || 0,
    parseInt(full.slice(2, 4), 16) || 0,
    parseInt(full.slice(4, 6), 16) || 0,
  ];
};
const withAlpha = (hex, a) => {
  const [r, g, b] = toRgb(hex);
  return "rgba(" + r + ", " + g + ", " + b + ", " + a + ")";
};
const darken = (hex, amount) => {
  const [r, g, b] = toRgb(hex);
  const f = (v) => Math.max(0, Math.round(v * (1 - amount)));
  return "rgb(" + f(r) + ", " + f(g) + ", " + f(b) + ")";
};

const formatSize = (bytes) => {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(0) + " KB";
  return (bytes / (1024 * 1024)).toFixed(1) + " MB";
};

const formatWhen = (iso) => {
  const d = new Date(iso);
  const now = new Date();
  const diffMin = Math.round((now.getTime() - d.getTime()) / 60000);
  if (diffMin <= 1) return "Just now";
  if (diffMin < 60) return diffMin + " min ago";
  const hhmm = ("0" + d.getHours()).slice(-2) + ":" + ("0" + d.getMinutes()).slice(-2);
  if (d.toDateString() === now.toDateString()) return "Today " + hhmm;
  const yest = new Date(now.getTime() - 86400000);
  if (d.toDateString() === yest.toDateString()) return "Yesterday " + hhmm;
  return d.getDate() + " " + MONTHS[d.getMonth()] + ", " + hhmm;
};

const extOf = (name) => {
  const parts = String(name).split(".");
  return parts.length > 1 ? parts.pop().toLowerCase() : "";
};

const kindLabel = (name) => {
  const e = extOf(name);
  if (e === "markdown") return "MD";
  return e ? e.toUpperCase() : "FILE";
};

const formatAgo = (s) => {
  if (s < 60) return s + "s ago";
  const m = Math.floor(s / 60);
  return m + "m " + (s % 60) + "s ago";
};

export default function Screen() {
  const navigate = useNavigate();
  const ink = darken(brand.neutralColor, 0.68);
  const body = darken(brand.neutralColor, 0.3);
  const muted = darken(brand.neutralColor, 0.12);
  const line = withAlpha(brand.neutralColor, 0.28);
  const primaryStrong = darken(brand.primaryColor, 0.1);
  const accentStrong = darken(brand.accentColor, 0.06);

  const [docs, setDocs] = React.useState([]);
  const [loadingDocs, setLoadingDocs] = React.useState(true);
  const [loadError, setLoadError] = React.useState(null);
  const [uploading, setUploading] = React.useState(false);
  const [deletingId, setDeletingId] = React.useState(null);
  const [query, setQuery] = React.useState("");
  const [filter, setFilter] = React.useState("all");
  const [notices, setNotices] = React.useState([]);
  const [confirmDoc, setConfirmDoc] = React.useState(null);
  const [dragging, setDragging] = React.useState(false);
  const [sinceSync, setSinceSync] = React.useState(0);
  const [lastSynced, setLastSynced] = React.useState(null);

  const fileInputRef = React.useRef(null);
  const cancelRef = React.useRef(null);
  const seq = React.useRef(0);
  const docsRef = React.useRef(docs);
  docsRef.current = docs;

  const pushNotice = React.useCallback((notice) => {
    seq.current += 1;
    setNotices((prev) => [{ id: "n" + seq.current, ...notice }, ...prev].slice(0, 5));
  }, []);
  const dismissNotice = (id) => setNotices((prev) => prev.filter((n) => n.id !== id));

  const fetchDocuments = React.useCallback(async () => {
    try {
      const data = await listDocuments();
      setDocs((prev) => {
        // Keep "isNew" animation markers for rows the caller just inserted,
        // so a background poll doesn't strip the entry animation.
        const newIds = new Set(prev.filter((d) => d.isNew).map((d) => d.id));
        return data.map((d) => (newIds.has(d.id) ? { ...d, isNew: true } : d));
      });
      setLoadError(null);
      setLastSynced(new Date());
    } catch (e) {
      setLoadError("Could not load the document library. Check your connection and try again.");
    } finally {
      setLoadingDocs(false);
    }
  }, []);

  React.useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  // Real status refresh: while anything is still processing, poll the shared
  // list so every visitor's screen converges on the same server state.
  React.useEffect(() => {
    const hasProcessing = docs.some((d) => d.status === "processing");
    if (!hasProcessing) return undefined;
    const timer = setInterval(fetchDocuments, POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [docs, fetchDocuments]);

  React.useEffect(() => {
    setSinceSync(0);
    const tick = setInterval(() => setSinceSync((s) => s + 1), 1000);
    return () => clearInterval(tick);
  }, [lastSynced]);

  React.useEffect(() => {
    if (confirmDoc && cancelRef.current) cancelRef.current.focus();
  }, [confirmDoc]);

  const counts = React.useMemo(() => {
    return {
      all: docs.length,
      ready: docs.filter((d) => d.status === "ready").length,
      processing: docs.filter((d) => d.status === "processing").length,
      failed: docs.filter((d) => d.status === "failed").length,
    };
  }, [docs]);

  const visible = React.useMemo(() => {
    const q = query.trim().toLowerCase();
    return docs.filter((d) => {
      const matchesFilter = filter === "all" || d.status === filter;
      const matchesQuery = !q || d.file_name.toLowerCase().includes(q);
      return matchesFilter && matchesQuery;
    });
  }, [docs, query, filter]);

  const stale = lastSynced !== null && sinceSync >= 45;

  const handleFiles = async (fileList) => {
    const files = Array.from(fileList || []);
    if (!files.length) return;

    const toUpload = [];
    files.forEach((file) => {
      const ext = extOf(file.name);
      if (ACCEPTED_EXTENSIONS.indexOf(ext) === -1) {
        pushNotice({
          tone: "error",
          title: file.name + " wasn't uploaded",
          detail:
            (ext ? "." + ext + " files aren't" : "Files without an extension aren't") +
            " supported. The library takes PDF, DOCX, TXT and Markdown.",
        });
        return;
      }
      if (file.size > MAX_FILE_BYTES) {
        pushNotice({
          tone: "error",
          title: file.name + " wasn't uploaded",
          detail:
            formatSize(file.size) +
            " is over the 25 MB per-file limit. Export it in parts and upload those.",
        });
        return;
      }
      toUpload.push(file);
    });

    if (!toUpload.length) return;

    setUploading(true);
    try {
      const result = await uploadDocuments(toUpload);
      const accepted = result.accepted || [];
      const rejected = result.rejected || [];

      if (accepted.length) {
        setDocs((prev) => [
          ...accepted.map((d) => ({
            id: d.id,
            file_name: d.file_name,
            size_bytes: d.size_bytes,
            uploaded_at: d.uploaded_at,
            status: d.status,
            failure_reason: null,
            chunk_count: 0,
            isNew: true,
          })),
          ...prev,
        ]);
        pushNotice({
          tone: "success",
          title:
            accepted.length === 1
              ? "1 file added — extracting text and embedding now"
              : accepted.length + " files added — extracting text and embedding now",
          detail:
            "Indexing runs on the server. You can close this tab or go and ask something; each file will reach ready or failed on its own.",
        });
      }

      rejected.forEach((r) =>
        pushNotice({ tone: "error", title: r.file_name + " wasn't uploaded", detail: r.reason }),
      );
    } catch (e) {
      pushNotice({
        tone: "error",
        title: "Upload failed",
        detail: "The server couldn't be reached, so nothing in this batch was uploaded. Try again.",
      });
    } finally {
      setUploading(false);
    }
  };

  const onDrop = (event) => {
    event.preventDefault();
    setDragging(false);
    handleFiles(event.dataTransfer && event.dataTransfer.files);
  };

  const confirmDelete = async () => {
    const doc = confirmDoc;
    if (!doc) return;
    setDeletingId(doc.id);
    try {
      await deleteDocument(doc.id);
      setDocs((prev) => prev.filter((d) => d.id !== doc.id));
      setConfirmDoc(null);
      pushNotice({
        tone: "info",
        title: doc.file_name + " deleted for everyone",
        detail:
          doc.status === "processing"
            ? "Indexing was stopped. Nothing was left behind in the search index."
            : (doc.chunk_count || 0) +
              " chunks and their embeddings were removed from the search index. Chat answers will stop citing it.",
      });
    } catch (e) {
      pushNotice({
        tone: "error",
        title: "Couldn't delete " + doc.file_name,
        detail: "The server didn't confirm the deletion. The document is still in the library — try again.",
      });
    } finally {
      setDeletingId(null);
    }
  };

  const statusMeta = (status) => {
    if (status === "ready")
      return {
        label: "Ready",
        text: accentStrong,
        bg: withAlpha(brand.accentColor, 0.1),
        border: withAlpha(brand.accentColor, 0.3),
        Icon: Icons.CheckCircle,
      };
    if (status === "failed")
      return {
        label: "Failed",
        text: primaryStrong,
        bg: withAlpha(brand.primaryColor, 0.1),
        border: withAlpha(brand.primaryColor, 0.3),
        Icon: Icons.AlertCircle,
      };
    return {
      label: "Indexing",
      text: body,
      bg: withAlpha(brand.neutralColor, 0.14),
      border: withAlpha(brand.neutralColor, 0.3),
      Icon: Icons.Clock,
    };
  };

  const noticeStyle = (tone) => {
    if (tone === "error")
      return {
        color: primaryStrong,
        bg: withAlpha(brand.primaryColor, 0.08),
        border: withAlpha(brand.primaryColor, 0.35),
        Icon: Icons.AlertCircle,
      };
    if (tone === "success")
      return {
        color: accentStrong,
        bg: withAlpha(brand.accentColor, 0.08),
        border: withAlpha(brand.accentColor, 0.32),
        Icon: Icons.CheckCircle,
      };
    return {
      color: body,
      bg: withAlpha(brand.neutralColor, 0.1),
      border: withAlpha(brand.neutralColor, 0.3),
      Icon: Icons.Trash,
    };
  };

  const card = {
    borderRadius: brand.radius,
    border: "1px solid " + line,
    backgroundColor: "#FFFFFF",
  };

  return (
    <div
      className="mx-auto w-full max-w-6xl px-4 pb-16 pt-6 sm:px-6"
      style={{ fontFamily: brand.fontBody, color: body, "--nb-accent": brand.accentColor }}
    >
      <style>{`
        .nb-focus:focus-visible { outline: 2px solid var(--nb-accent); outline-offset: 2px; }
        @keyframes nb-in { from { opacity: 0; transform: translateY(-8px); } to { opacity: 1; transform: none; } }
        .nb-in { animation: nb-in .34s cubic-bezier(.22,.8,.3,1) both; }
        @keyframes nb-pulse { 0%,100% { opacity: 1; } 50% { opacity: .3; } }
        .nb-pulse { animation: nb-pulse 1.8s ease-in-out infinite; }
        .nb-bar > span { transition: width .7s ease; }
        @media (prefers-reduced-motion: reduce) {
          .nb-in, .nb-pulse { animation: none; }
          .nb-bar > span { transition: none; }
        }
      `}</style>

      {/* Header */}
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-[0.14em]" style={{ color: muted }}>
            Shared board · no accounts
          </p>
          <h1
            className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl"
            style={{ fontFamily: brand.fontHeading, color: ink }}
          >
            Document library
          </h1>
          <p className="mt-2 max-w-xl text-base leading-relaxed">
            Everything here is what the assistant can answer from. Anyone with the link sees this
            same board — and can add to it or clear it.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            className="nb-focus"
            onClick={() => navigate("chat")}
            style={{
              backgroundColor: "transparent",
              color: accentStrong,
              border: "1px solid " + withAlpha(brand.accentColor, 0.45),
              borderRadius: brand.radius,
            }}
          >
            <span className="inline-flex items-center gap-2">
              Ask about these documents
              <Icons.ChevronRight className="h-4 w-4" aria-hidden="true" />
            </span>
          </Button>
          <Button
            className="nb-focus"
            onClick={() => navigate("setup")}
            style={{
              backgroundColor: "transparent",
              color: muted,
              border: "1px solid " + line,
              borderRadius: brand.radius,
            }}
          >
            <span className="inline-flex items-center gap-2">
              <Icons.Settings className="h-4 w-4" aria-hidden="true" />
              Setup &amp; status
            </span>
          </Button>
        </div>
      </header>

      {/* Upload board — the focal point */}
      <section aria-labelledby="upload-heading" className="mt-8">
        <h2 id="upload-heading" className="sr-only">
          Add documents
        </h2>
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          className="px-6 py-10 text-center transition-colors duration-200 sm:px-10 sm:py-14"
          style={{
            borderRadius: brand.radius,
            border:
              "2px dashed " + (dragging ? brand.primaryColor : withAlpha(brand.primaryColor, 0.38)),
            backgroundColor: dragging
              ? withAlpha(brand.primaryColor, 0.08)
              : withAlpha(brand.primaryColor, 0.03),
          }}
        >
          <span
            className="mx-auto flex h-14 w-14 items-center justify-center"
            style={{
              borderRadius: brand.radius,
              backgroundColor: withAlpha(brand.primaryColor, 0.12),
              color: primaryStrong,
            }}
          >
            <Icons.Upload className="h-7 w-7" aria-hidden="true" />
          </span>
          <p
            className="mt-5 text-xl font-semibold sm:text-2xl"
            style={{ fontFamily: brand.fontHeading, color: ink }}
          >
            {uploading ? "Uploading…" : "Pin a document to the board"}
          </p>
          <p className="mx-auto mt-2 max-w-md text-sm leading-relaxed sm:text-base">
            {uploading
              ? "Sending files to the server. Accepted files will appear below as soon as the server confirms them."
              : "Drop files here, or pick several at once. PDF, DOCX, TXT and Markdown, up to 25 MB each."}
          </p>

          <label className="sr-only" htmlFor="document-files">
            Choose PDF, DOCX, TXT or Markdown files to upload
          </label>
          <input
            id="document-files"
            ref={fileInputRef}
            type="file"
            multiple
            accept=".pdf,.docx,.txt,.md,.markdown"
            className="sr-only"
            disabled={uploading}
            onChange={(e) => {
              handleFiles(e.target.files);
              e.target.value = "";
            }}
          />
          <div className="mt-6 flex flex-col items-center gap-3">
            <button
              type="button"
              className="nb-focus inline-flex w-full items-center justify-center gap-2 px-6 py-3 text-base font-semibold transition-transform duration-150 active:scale-[.98] disabled:cursor-not-allowed sm:w-auto"
              disabled={uploading}
              onClick={() => fileInputRef.current && fileInputRef.current.click()}
              style={{
                borderRadius: brand.radius,
                backgroundColor: uploading ? withAlpha(brand.neutralColor, 0.25) : primaryStrong,
                color: uploading ? muted : "#FFFFFF",
              }}
            >
              <Icons.Plus className="h-5 w-5" aria-hidden="true" />
              Choose files
            </button>
            <p className="text-xs tabular-nums" style={{ color: muted }}>
              {docs.length} document{docs.length === 1 ? "" : "s"} in the library · {counts.ready}{" "}
              ready to answer from
            </p>
          </div>
        </div>
      </section>

      {/* Notices: rejections, uploads, deletions */}
      {notices.length > 0 && (
        <section aria-live="polite" className="mt-4 space-y-2">
          <h2 className="sr-only">Upload and deletion messages</h2>
          <ul className="space-y-2">
            {notices.map((n) => {
              const s = noticeStyle(n.tone);
              return (
                <li
                  key={n.id}
                  className="nb-in flex items-start gap-3 px-4 py-3"
                  style={{
                    borderRadius: brand.radius,
                    backgroundColor: s.bg,
                    border: "1px solid " + s.border,
                  }}
                >
                  <s.Icon
                    className="mt-0.5 h-5 w-5 shrink-0"
                    style={{ color: s.color }}
                    aria-hidden="true"
                  />
                  <div className="min-w-0 flex-1">
                    <p className="break-words text-sm font-semibold" style={{ color: s.color }}>
                      {n.title}
                    </p>
                    <p className="mt-0.5 text-sm leading-relaxed">{n.detail}</p>
                  </div>
                  <button
                    type="button"
                    className="nb-focus shrink-0 p-1"
                    style={{ borderRadius: brand.radius, color: muted }}
                    onClick={() => dismissNotice(n.id)}
                    aria-label={"Dismiss message: " + n.title}
                  >
                    <Icons.X className="h-4 w-4" aria-hidden="true" />
                  </button>
                </li>
              );
            })}
          </ul>
        </section>
      )}

      {/* Library */}
      <section aria-labelledby="library-heading" className="mt-10">
        <div className="flex flex-wrap items-baseline justify-between gap-3">
          <h2
            id="library-heading"
            className="text-xl font-semibold"
            style={{ fontFamily: brand.fontHeading, color: ink }}
          >
            On the board
          </h2>
          <div className="flex items-center gap-2 text-xs" style={{ color: muted }}>
            {loadingDocs ? (
              <span>Loading…</span>
            ) : stale ? (
              <>
                <span
                  className="inline-block h-2 w-2 rounded-full"
                  style={{ backgroundColor: withAlpha(brand.neutralColor, 0.6) }}
                  aria-hidden="true"
                />
                <span className="tabular-nums">Last checked {formatAgo(sinceSync)}</span>
                <button
                  type="button"
                  className="nb-focus px-2 py-1 font-semibold"
                  style={{
                    borderRadius: brand.radius,
                    color: accentStrong,
                    border: "1px solid " + withAlpha(brand.accentColor, 0.4),
                  }}
                  onClick={() => fetchDocuments()}
                >
                  Check now
                </button>
              </>
            ) : (
              <>
                <span
                  className="nb-pulse inline-block h-2 w-2 rounded-full"
                  style={{ backgroundColor: brand.accentColor }}
                  aria-hidden="true"
                />
                <span className="tabular-nums">Live · updated {formatAgo(sinceSync)}</span>
                <button
                  type="button"
                  className="nb-focus px-2 py-1 font-semibold"
                  style={{
                    borderRadius: brand.radius,
                    color: accentStrong,
                    border: "1px solid " + withAlpha(brand.accentColor, 0.4),
                  }}
                  onClick={() => fetchDocuments()}
                >
                  Refresh
                </button>
              </>
            )}
          </div>
        </div>

        {loadError && (
          <div
            className="mt-4 flex items-start gap-3 px-4 py-3"
            style={{
              borderRadius: brand.radius,
              backgroundColor: withAlpha(brand.primaryColor, 0.08),
              border: "1px solid " + withAlpha(brand.primaryColor, 0.35),
            }}
            role="alert"
          >
            <Icons.AlertCircle
              className="mt-0.5 h-5 w-5 shrink-0"
              style={{ color: primaryStrong }}
              aria-hidden="true"
            />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold" style={{ color: primaryStrong }}>
                {loadError}
              </p>
            </div>
            <button
              type="button"
              className="nb-focus shrink-0 px-3 py-1 text-sm font-semibold"
              style={{
                borderRadius: brand.radius,
                color: accentStrong,
                border: "1px solid " + withAlpha(brand.accentColor, 0.4),
              }}
              onClick={() => fetchDocuments()}
            >
              Retry
            </button>
          </div>
        )}

        <div className="mt-4 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <span
              id="filter-label"
              className="mb-2 block text-xs font-semibold uppercase tracking-wide"
              style={{ color: muted }}
            >
              Filter by status
            </span>
            <div className="flex flex-wrap gap-2" role="group" aria-labelledby="filter-label">
              {FILTERS.map((f) => {
                const active = filter === f.key;
                return (
                  <button
                    key={f.key}
                    type="button"
                    aria-pressed={active}
                    onClick={() => setFilter(f.key)}
                    className="nb-focus px-4 py-2 text-sm font-medium transition-colors duration-150"
                    style={{
                      borderRadius: brand.radius,
                      backgroundColor: active ? withAlpha(brand.accentColor, 0.12) : "#FFFFFF",
                      border: "1px solid " + (active ? withAlpha(brand.accentColor, 0.5) : line),
                      color: active ? accentStrong : body,
                    }}
                  >
                    {f.label}
                    <span
                      className="ml-2 tabular-nums"
                      style={{ color: active ? accentStrong : muted }}
                    >
                      {counts[f.key]}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="lg:w-72">
            <Label htmlFor="doc-search">Search file names</Label>
            <div className="relative mt-1">
              <Icons.Search
                className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2"
                style={{ color: muted }}
                aria-hidden="true"
              />
              <Input
                id="doc-search"
                type="search"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="handbook, contract, policy…"
                className="nb-focus w-full pl-9"
                style={{
                  borderRadius: brand.radius,
                  borderColor: line,
                  backgroundColor: "#FFFFFF",
                }}
              />
            </div>
          </div>
        </div>

        {/* List / empty states */}
        {loadingDocs ? (
          <div className="mt-6 px-6 py-16 text-center" style={card}>
            <p className="text-sm leading-relaxed" style={{ color: muted }}>
              Loading the document library…
            </p>
          </div>
        ) : docs.length === 0 ? (
          <div className="mt-6 px-6 py-16 text-center" style={card}>
            <span
              className="mx-auto flex h-12 w-12 items-center justify-center"
              style={{
                borderRadius: brand.radius,
                backgroundColor: withAlpha(brand.neutralColor, 0.12),
                color: body,
              }}
            >
              <Icons.FileText className="h-6 w-6" aria-hidden="true" />
            </span>
            <h3
              className="mt-4 text-lg font-semibold"
              style={{ fontFamily: brand.fontHeading, color: ink }}
            >
              The board is empty
            </h3>
            <p className="mx-auto mt-2 max-w-sm text-sm leading-relaxed">
              The assistant only knows what is pinned here. Upload a PDF, DOCX, TXT or Markdown file
              and it will be split, embedded and ready to answer questions within a minute or two.
            </p>
          </div>
        ) : visible.length === 0 ? (
          <div className="mt-6 px-6 py-14 text-center" style={card}>
            <h3
              className="text-lg font-semibold"
              style={{ fontFamily: brand.fontHeading, color: ink }}
            >
              Nothing matches that
            </h3>
            <p className="mx-auto mt-2 max-w-sm text-sm leading-relaxed">
              {query.trim()
                ? 'No file name contains "' +
                  query.trim() +
                  '"' +
                  (filter !== "all" ? " with status " + filter + "." : ".")
                : "No documents are " + filter + " right now."}
            </p>
            <button
              type="button"
              className="nb-focus mt-5 px-4 py-2 text-sm font-semibold"
              style={{
                borderRadius: brand.radius,
                color: accentStrong,
                border: "1px solid " + withAlpha(brand.accentColor, 0.45),
              }}
              onClick={() => {
                setQuery("");
                setFilter("all");
              }}
            >
              Show all {docs.length} documents
            </button>
          </div>
        ) : (
          <ul className="mt-6 grid gap-4 md:grid-cols-2">
            {visible.map((doc) => {
              const meta = statusMeta(doc.status);
              return (
                <li
                  key={doc.id}
                  className={"flex flex-col p-4 sm:p-5" + (doc.isNew ? " nb-in" : "")}
                  style={card}
                >
                  <div className="flex items-start gap-3">
                    <span
                      className="flex h-11 w-11 shrink-0 items-center justify-center"
                      style={{
                        borderRadius: brand.radius,
                        backgroundColor: meta.bg,
                        color: meta.text,
                      }}
                    >
                      <Icons.FileText className="h-5 w-5" aria-hidden="true" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <h3
                        className="truncate text-base font-semibold"
                        style={{ color: ink }}
                        title={doc.file_name}
                      >
                        {doc.file_name}
                      </h3>
                      <p className="mt-1 text-sm tabular-nums" style={{ color: muted }}>
                        {kindLabel(doc.file_name)} · {formatSize(doc.size_bytes)} ·{" "}
                        {formatWhen(doc.uploaded_at)}
                      </p>
                    </div>
                    <button
                      type="button"
                      className="nb-focus shrink-0 p-2 transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-50"
                      style={{ borderRadius: brand.radius, color: muted }}
                      disabled={deletingId === doc.id}
                      onClick={() => setConfirmDoc(doc)}
                      aria-label={"Delete " + doc.file_name + " from the shared library"}
                    >
                      <Icons.Trash className="h-4 w-4" aria-hidden="true" />
                    </button>
                  </div>

                  <div className="mt-4 flex flex-wrap items-center gap-2">
                    <span
                      className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-semibold"
                      style={{
                        borderRadius: brand.radius,
                        backgroundColor: meta.bg,
                        color: meta.text,
                        border: "1px solid " + meta.border,
                      }}
                    >
                      <meta.Icon className="h-3.5 w-3.5" aria-hidden="true" />
                      {meta.label}
                    </span>
                    {doc.status === "ready" && (
                      <span className="text-sm tabular-nums">
                        {doc.chunk_count} chunks indexed · searchable in chat
                      </span>
                    )}
                    {doc.status === "processing" && (
                      <span className="text-sm tabular-nums">Embedding with Gemini…</span>
                    )}
                  </div>

                  {doc.status === "processing" && (
                    <div
                      className="nb-bar mt-3 h-2 w-full overflow-hidden"
                      style={{
                        borderRadius: brand.radius,
                        backgroundColor: withAlpha(brand.neutralColor, 0.16),
                      }}
                      role="progressbar"
                      aria-valuemin={0}
                      aria-valuemax={100}
                      aria-label={"Indexing " + doc.file_name}
                    >
                      <span
                        className="nb-pulse block h-full w-full"
                        style={{ backgroundColor: brand.accentColor }}
                      />
                    </div>
                  )}

                  {doc.status === "failed" && (
                    <p
                      className="mt-3 px-3 py-2 text-sm leading-relaxed"
                      style={{
                        borderRadius: brand.radius,
                        backgroundColor: withAlpha(brand.primaryColor, 0.07),
                        color: body,
                      }}
                    >
                      {doc.failure_reason}
                    </p>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </section>

      {/* House rules */}
      <section
        aria-labelledby="rules-heading"
        className="mt-10 p-5"
        style={{ ...card, backgroundColor: withAlpha(brand.neutralColor, 0.06) }}
      >
        <h2
          id="rules-heading"
          className="text-sm font-semibold uppercase tracking-wide"
          style={{ color: ink }}
        >
          How this board works
        </h2>
        <ul className="mt-3 grid gap-2 text-sm leading-relaxed sm:grid-cols-2">
          <li className="flex items-start gap-2">
            <Icons.Users
              className="mt-0.5 h-4 w-4 shrink-0"
              style={{ color: muted }}
              aria-hidden="true"
            />
            <span>
              No logins. Anyone with the link can upload or delete, and nothing records who did it.
            </span>
          </li>
          <li className="flex items-start gap-2">
            <Icons.AlertCircle
              className="mt-0.5 h-4 w-4 shrink-0"
              style={{ color: muted }}
              aria-hidden="true"
            />
            <span>Scanned, image-only PDFs fail: there is no OCR in this release.</span>
          </li>
          <li className="flex items-start gap-2">
            <Icons.Clock
              className="mt-0.5 h-4 w-4 shrink-0"
              style={{ color: muted }}
              aria-hidden="true"
            />
            <span className="tabular-nums">
              Uploads are rate-limited per connection to protect the Gemini quota.
            </span>
          </li>
          <li className="flex items-start gap-2">
            <Icons.Settings
              className="mt-0.5 h-4 w-4 shrink-0"
              style={{ color: muted }}
              aria-hidden="true"
            />
            <span>
              The API key, document cap and limits are set by the operator —{" "}
              <button
                type="button"
                className="nb-focus font-semibold underline underline-offset-2"
                style={{ color: accentStrong, borderRadius: brand.radius }}
                onClick={() => navigate("setup")}
              >
                see setup &amp; status
              </button>
              .
            </span>
          </li>
        </ul>
      </section>

      {/* Delete confirmation */}
      {confirmDoc && (
        <div
          className="fixed inset-0 z-50 flex items-end justify-center p-4 sm:items-center"
          style={{ backgroundColor: withAlpha(ink, 0.45) }}
          onMouseDown={(e) => {
            if (e.target === e.currentTarget) setConfirmDoc(null);
          }}
          onKeyDown={(e) => {
            if (e.key === "Escape") setConfirmDoc(null);
          }}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-title"
            aria-describedby="delete-desc"
            className="nb-in w-full max-w-md p-6"
            style={{
              borderRadius: brand.radius,
              backgroundColor: brand.backgroundColor,
              border: "1px solid " + line,
            }}
          >
            <h2
              id="delete-title"
              className="text-lg font-semibold"
              style={{ fontFamily: brand.fontHeading, color: ink }}
            >
              Delete this for everyone?
            </h2>
            <p className="mt-2 break-words text-sm font-medium" style={{ color: ink }}>
              {confirmDoc.file_name}
            </p>
            <p id="delete-desc" className="mt-3 text-sm leading-relaxed">
              {confirmDoc.status === "processing"
                ? "Indexing is still running. Deleting stops it and discards the chunks embedded so far."
                : confirmDoc.status === "failed"
                  ? "This document has no chunks in the index, so chat answers will not change."
                  : "Its " +
                    (confirmDoc.chunk_count || 0) +
                    " chunks and embeddings go too, so answers will stop citing it."}{" "}
              This board is shared with everyone who has the link. There is no undo and no copy
              kept.
            </p>
            <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
              <button
                type="button"
                ref={cancelRef}
                className="nb-focus px-4 py-2.5 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60"
                style={{
                  borderRadius: brand.radius,
                  border: "1px solid " + line,
                  color: body,
                  backgroundColor: "#FFFFFF",
                }}
                disabled={deletingId === confirmDoc.id}
                onClick={() => setConfirmDoc(null)}
              >
                Keep it
              </button>
              <button
                type="button"
                className="nb-focus px-4 py-2.5 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60"
                style={{
                  borderRadius: brand.radius,
                  backgroundColor: primaryStrong,
                  color: "#FFFFFF",
                }}
                disabled={deletingId === confirmDoc.id}
                onClick={confirmDelete}
              >
                {deletingId === confirmDoc.id ? "Deleting…" : "Delete permanently"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
