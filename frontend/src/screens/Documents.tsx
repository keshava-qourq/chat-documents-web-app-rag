// @ts-nocheck -- generated from the approved design under its JS runtime contract; not hand-written TypeScript.
/* eslint-disable @typescript-eslint/no-unused-vars */
import React from "react";

import * as UI from "@/lib/ui";
import { Icons } from "@/lib/icons";
import { brand } from "@/lib/brand";
import { useNavigate } from "@/lib/navigate";

const { Button, Input, Label } = UI;
const { Plus, Search, Check, X, ChevronRight, Users, Settings, FileText, Clock, Trash, Filter, Upload, AlertCircle, CheckCircle } = Icons;

const MAX_FILE_BYTES = 25 * 1024 * 1024;
const MAX_DOCUMENTS = 12;
const ACCEPTED_EXTENSIONS = ["pdf", "docx", "txt", "md", "markdown"];
const MIME_BY_EXT = {
  pdf: "application/pdf",
  docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  txt: "text/plain",
  md: "text/markdown",
  markdown: "text/markdown",
};
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const REFERENCE_NOW = new Date("2026-10-16T10:45:00");

const INITIAL_DOCUMENTS = [
  {
    id: "doc_8812",
    file_name: "Supplier contract — Larkfield Mills.pdf",
    mime_type: "application/pdf",
    size_bytes: 9441020,
    status: "processing",
    progress: 58,
    failure_reason: null,
    chunk_count: null,
    uploaded_at: "2026-10-16T10:36:00",
    planned_chunks: 304,
  },
  {
    id: "doc_8810",
    file_name: "Customer interviews — week 41.docx",
    mime_type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    size_bytes: 2880110,
    status: "processing",
    progress: 21,
    failure_reason: null,
    chunk_count: null,
    uploaded_at: "2026-10-16T10:31:00",
    planned_chunks: 97,
  },
  {
    id: "doc_8807",
    file_name: "Warehouse safety audit (scanned).pdf",
    mime_type: "application/pdf",
    size_bytes: 12908441,
    status: "failed",
    progress: 100,
    failure_reason:
      "No extractable text found. Scanned, image-only PDFs can't be read in this release — there is no OCR.",
    chunk_count: 0,
    uploaded_at: "2026-10-16T07:58:00",
  },
  {
    id: "doc_8805",
    file_name: "Support escalation matrix.md",
    mime_type: "text/markdown",
    size_bytes: 38210,
    status: "ready",
    progress: 100,
    failure_reason: null,
    chunk_count: 14,
    uploaded_at: "2026-10-16T08:05:00",
  },
  {
    id: "doc_8799",
    file_name: "Onboarding handbook v4.pdf",
    mime_type: "application/pdf",
    size_bytes: 4812332,
    status: "ready",
    progress: 100,
    failure_reason: null,
    chunk_count: 218,
    uploaded_at: "2026-10-15T09:12:00",
  },
  {
    id: "doc_8794",
    file_name: "Q3-2026 board summary.docx",
    mime_type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    size_bytes: 1204880,
    status: "ready",
    progress: 100,
    failure_reason: null,
    chunk_count: 96,
    uploaded_at: "2026-10-14T16:40:00",
  },
  {
    id: "doc_8788",
    file_name: "Annual report 2025.pdf",
    mime_type: "application/pdf",
    size_bytes: 18220904,
    status: "failed",
    progress: 100,
    failure_reason:
      "Embedding service error — Gemini returned 503 on three retries. Nothing was left in the index; upload it again to retry.",
    chunk_count: 0,
    uploaded_at: "2026-10-13T14:02:00",
  },
  {
    id: "doc_8781",
    file_name: "Release notes 12.4.md",
    mime_type: "text/markdown",
    size_bytes: 11002,
    status: "ready",
    progress: 100,
    failure_reason: null,
    chunk_count: 5,
    uploaded_at: "2026-10-12T17:45:00",
  },
  {
    id: "doc_8775",
    file_name: "Field service checklist.docx",
    mime_type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    size_bytes: 640221,
    status: "ready",
    progress: 100,
    failure_reason: null,
    chunk_count: 31,
    uploaded_at: "2026-10-11T11:03:00",
  },
  {
    id: "doc_8768",
    file_name: "Expenses policy 2026.txt",
    mime_type: "text/plain",
    size_bytes: 21904,
    status: "ready",
    progress: 100,
    failure_reason: null,
    chunk_count: 9,
    uploaded_at: "2026-10-09T11:21:00",
  },
];

const FILTERS = [
  { key: "all", label: "All" },
  { key: "ready", label: "Ready" },
  { key: "processing", label: "Indexing" },
  { key: "failed", label: "Failed" },
];

const toRgb = (hex) => {
  const h = String(hex || "#000000").replace("#", "");
  const full = h.length === 3 ? h.split("").map((c) => c + c).join("") : h;
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
  const diffMin = Math.round((REFERENCE_NOW.getTime() - d.getTime()) / 60000);
  if (diffMin <= 1) return "Just now";
  if (diffMin < 60) return diffMin + " min ago";
  const hhmm = ("0" + d.getHours()).slice(-2) + ":" + ("0" + d.getMinutes()).slice(-2);
  if (d.toDateString() === REFERENCE_NOW.toDateString()) return "Today " + hhmm;
  const yest = new Date(REFERENCE_NOW.getTime() - 86400000);
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

  const [docs, setDocs] = React.useState(INITIAL_DOCUMENTS);
  const [query, setQuery] = React.useState("");
  const [filter, setFilter] = React.useState("all");
  const [notices, setNotices] = React.useState([]);
  const [confirmDoc, setConfirmDoc] = React.useState(null);
  const [dragging, setDragging] = React.useState(false);
  const [sinceSync, setSinceSync] = React.useState(4);

  const fileInputRef = React.useRef(null);
  const cancelRef = React.useRef(null);
  const seq = React.useRef(0);

  // Background indexing: processing documents advance and settle on their own.
  React.useEffect(() => {
    const tick = setInterval(() => {
      setDocs((prev) => {
        let changed = false;
        const next = prev.map((d) => {
          if (d.status !== "processing") return d;
          changed = true;
          const p = (d.progress || 0) + 6 + Math.round(Math.random() * 10);
          if (p >= 100) {
            if (d.will_fail) {
              return {
                ...d,
                status: "failed",
                progress: 100,
                chunk_count: 0,
                failure_reason:
                  "No extractable text found. Scanned, image-only PDFs can't be read in this release — there is no OCR.",
              };
            }
            return {
              ...d,
              status: "ready",
              progress: 100,
              chunk_count: d.planned_chunks || Math.max(4, Math.round(d.size_bytes / 24000)),
            };
          }
          return { ...d, progress: p };
        });
        return changed ? next : prev;
      });
    }, 900);
    return () => clearInterval(tick);
  }, []);

  React.useEffect(() => {
    const tick = setInterval(() => setSinceSync((s) => s + 1), 1000);
    return () => clearInterval(tick);
  }, []);

  React.useEffect(() => {
    setSinceSync(0);
  }, [docs]);

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

  const libraryFull = docs.length >= MAX_DOCUMENTS;
  const stale = sinceSync >= 45;

  const pushNotice = (notice) => {
    seq.current += 1;
    setNotices((prev) => [{ id: "n" + seq.current, ...notice }, ...prev].slice(0, 5));
  };
  const dismissNotice = (id) => setNotices((prev) => prev.filter((n) => n.id !== id));

  const handleFiles = (fileList) => {
    const files = Array.from(fileList || []);
    if (!files.length) return;
    let slots = MAX_DOCUMENTS - docs.length;
    const accepted = [];
    const rejected = [];

    files.forEach((file, i) => {
      const ext = extOf(file.name);
      if (ACCEPTED_EXTENSIONS.indexOf(ext) === -1) {
        rejected.push({
          name: file.name,
          reason:
            (ext ? "." + ext + " files aren't" : "Files without an extension aren't") +
            " supported. The library takes PDF, DOCX, TXT and Markdown.",
        });
        return;
      }
      if (file.size > MAX_FILE_BYTES) {
        rejected.push({
          name: file.name,
          reason:
            formatSize(file.size) + " is over the 25 MB per-file limit. Export it in parts and upload those.",
        });
        return;
      }
      if (slots <= 0) {
        rejected.push({
          name: file.name,
          reason:
            "The board is full at " +
            MAX_DOCUMENTS +
            " documents. Delete something below and this file will upload fine.",
        });
        return;
      }
      slots -= 1;
      seq.current += 1;
      accepted.push({
        id: "doc_new_" + seq.current + "_" + i,
        file_name: file.name,
        mime_type: MIME_BY_EXT[ext] || file.type || "application/octet-stream",
        size_bytes: file.size,
        status: "processing",
        progress: 2,
        failure_reason: null,
        chunk_count: null,
        uploaded_at: new Date(REFERENCE_NOW.getTime() - 20000).toISOString(),
        will_fail: /scan|photo/i.test(file.name) && ext === "pdf",
        isNew: true,
      });
    });

    if (accepted.length) {
      setDocs((prev) => [...accepted, ...prev]);
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
    rejected.forEach((r) => pushNotice({ tone: "error", title: r.name + " wasn't uploaded", detail: r.reason }));
  };

  const onDrop = (event) => {
    event.preventDefault();
    setDragging(false);
    if (libraryFull) {
      pushNotice({
        tone: "error",
        title: "Nothing uploaded — the board is full",
        detail:
          "The library holds its maximum of " +
          MAX_DOCUMENTS +
          " documents. Delete one below, then drop these again.",
      });
      return;
    }
    handleFiles(event.dataTransfer && event.dataTransfer.files);
  };

  const confirmDelete = () => {
    const doc = confirmDoc;
    if (!doc) return;
    setDocs((prev) => prev.filter((d) => d.id !== doc.id));
    setConfirmDoc(null);
    pushNotice({
      tone: "info",
      title: doc.file_name + " deleted for everyone",
      detail:
        doc.status === "processing"
          ? "Indexing was stopped and the chunks embedded so far were discarded. Nothing was left behind in the search index."
          : (doc.chunk_count || 0) +
            " chunks and their embeddings were removed from the search index. Chat answers will stop citing it.",
    });
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
      return { color: primaryStrong, bg: withAlpha(brand.primaryColor, 0.08), border: withAlpha(brand.primaryColor, 0.35), Icon: Icons.AlertCircle };
    if (tone === "success")
      return { color: accentStrong, bg: withAlpha(brand.accentColor, 0.08), border: withAlpha(brand.accentColor, 0.32), Icon: Icons.CheckCircle };
    return { color: body, bg: withAlpha(brand.neutralColor, 0.1), border: withAlpha(brand.neutralColor, 0.3), Icon: Icons.Trash };
  };

  const card = { borderRadius: brand.radius, border: "1px solid " + line, backgroundColor: "#FFFFFF" };

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
            Everything here is what the assistant can answer from. Anyone with the link sees this same board — and can
            add to it or clear it.
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
            if (!libraryFull) setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          className="px-6 py-10 text-center transition-colors duration-200 sm:px-10 sm:py-14"
          style={{
            borderRadius: brand.radius,
            border: "2px dashed " + (dragging ? brand.primaryColor : withAlpha(brand.primaryColor, 0.38)),
            backgroundColor: dragging ? withAlpha(brand.primaryColor, 0.08) : withAlpha(brand.primaryColor, 0.03),
          }}
        >
          <span
            className="mx-auto flex h-14 w-14 items-center justify-center"
            style={{ borderRadius: brand.radius, backgroundColor: withAlpha(brand.primaryColor, 0.12), color: primaryStrong }}
          >
            <Icons.Upload className="h-7 w-7" aria-hidden="true" />
          </span>
          <p className="mt-5 text-xl font-semibold sm:text-2xl" style={{ fontFamily: brand.fontHeading, color: ink }}>
            {libraryFull ? "The board is full" : "Pin a document to the board"}
          </p>
          <p className="mx-auto mt-2 max-w-md text-sm leading-relaxed sm:text-base">
            {libraryFull
              ? "There are " +
                MAX_DOCUMENTS +
                " of " +
                MAX_DOCUMENTS +
                " documents stored. Delete one below and uploading works again straight away — no restart needed."
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
            onChange={(e) => {
              handleFiles(e.target.files);
              e.target.value = "";
            }}
          />
          <div className="mt-6 flex flex-col items-center gap-3">
            <button
              type="button"
              className="nb-focus inline-flex w-full items-center justify-center gap-2 px-6 py-3 text-base font-semibold transition-transform duration-150 active:scale-[.98] disabled:cursor-not-allowed sm:w-auto"
              disabled={libraryFull}
              onClick={() => fileInputRef.current && fileInputRef.current.click()}
              style={{
                borderRadius: brand.radius,
                backgroundColor: libraryFull ? withAlpha(brand.neutralColor, 0.25) : primaryStrong,
                color: libraryFull ? muted : "#FFFFFF",
              }}
            >
              <Icons.Plus className="h-5 w-5" aria-hidden="true" />
              Choose files
            </button>
            <p className="text-xs tabular-nums" style={{ color: muted }}>
              {docs.length} of {MAX_DOCUMENTS} documents stored · {counts.ready} ready to answer from
            </p>
            <div
              className="h-1.5 w-full max-w-xs overflow-hidden"
              style={{ borderRadius: brand.radius, backgroundColor: withAlpha(brand.neutralColor, 0.18) }}
              role="img"
              aria-label={docs.length + " of " + MAX_DOCUMENTS + " document slots used"}
            >
              <span
                className="block h-full"
                style={{
                  width: Math.min(100, (docs.length / MAX_DOCUMENTS) * 100) + "%",
                  backgroundColor: libraryFull ? primaryStrong : brand.accentColor,
                }}
              />
            </div>
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
                  style={{ borderRadius: brand.radius, backgroundColor: s.bg, border: "1px solid " + s.border }}
                >
                  <s.Icon className="mt-0.5 h-5 w-5 shrink-0" style={{ color: s.color }} aria-hidden="true" />
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
          <h2 id="library-heading" className="text-xl font-semibold" style={{ fontFamily: brand.fontHeading, color: ink }}>
            On the board
          </h2>
          <div className="flex items-center gap-2 text-xs" style={{ color: muted }}>
            {stale ? (
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
                  style={{ borderRadius: brand.radius, color: accentStrong, border: "1px solid " + withAlpha(brand.accentColor, 0.4) }}
                  onClick={() => setSinceSync(0)}
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
              </>
            )}
          </div>
        </div>

        <div className="mt-4 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <span id="filter-label" className="mb-2 block text-xs font-semibold uppercase tracking-wide" style={{ color: muted }}>
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
                    <span className="ml-2 tabular-nums" style={{ color: active ? accentStrong : muted }}>
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
                style={{ borderRadius: brand.radius, borderColor: line, backgroundColor: "#FFFFFF" }}
              />
            </div>
          </div>
        </div>

        {/* List / empty states */}
        {docs.length === 0 ? (
          <div className="mt-6 px-6 py-16 text-center" style={card}>
            <span
              className="mx-auto flex h-12 w-12 items-center justify-center"
              style={{ borderRadius: brand.radius, backgroundColor: withAlpha(brand.neutralColor, 0.12), color: body }}
            >
              <Icons.FileText className="h-6 w-6" aria-hidden="true" />
            </span>
            <h3 className="mt-4 text-lg font-semibold" style={{ fontFamily: brand.fontHeading, color: ink }}>
              The board is empty
            </h3>
            <p className="mx-auto mt-2 max-w-sm text-sm leading-relaxed">
              The assistant only knows what is pinned here. Upload a PDF, DOCX, TXT or Markdown file and it will be
              split, embedded and ready to answer questions within a minute or two.
            </p>
          </div>
        ) : visible.length === 0 ? (
          <div className="mt-6 px-6 py-14 text-center" style={card}>
            <h3 className="text-lg font-semibold" style={{ fontFamily: brand.fontHeading, color: ink }}>
              Nothing matches that
            </h3>
            <p className="mx-auto mt-2 max-w-sm text-sm leading-relaxed">
              {query.trim()
                ? 'No file name contains "' + query.trim() + '"' + (filter !== "all" ? " with status " + filter + "." : ".")
                : "No documents are " + filter + " right now."}
            </p>
            <button
              type="button"
              className="nb-focus mt-5 px-4 py-2 text-sm font-semibold"
              style={{ borderRadius: brand.radius, color: accentStrong, border: "1px solid " + withAlpha(brand.accentColor, 0.45) }}
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
                      style={{ borderRadius: brand.radius, backgroundColor: meta.bg, color: meta.text }}
                    >
                      <Icons.FileText className="h-5 w-5" aria-hidden="true" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <h3 className="truncate text-base font-semibold" style={{ color: ink }} title={doc.file_name}>
                        {doc.file_name}
                      </h3>
                      <p className="mt-1 text-sm tabular-nums" style={{ color: muted }}>
                        {kindLabel(doc.file_name)} · {formatSize(doc.size_bytes)} · {formatWhen(doc.uploaded_at)}
                      </p>
                    </div>
                    <button
                      type="button"
                      className="nb-focus shrink-0 p-2 transition-colors duration-150"
                      style={{ borderRadius: brand.radius, color: muted }}
                      onClick={() => setConfirmDoc(doc)}
                      aria-label={"Delete " + doc.file_name + " from the shared library"}
                    >
                      <Icons.Trash className="h-4 w-4" aria-hidden="true" />
                    </button>
                  </div>

                  <div className="mt-4 flex flex-wrap items-center gap-2">
                    <span
                      className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-semibold"
                      style={{ borderRadius: brand.radius, backgroundColor: meta.bg, color: meta.text, border: "1px solid " + meta.border }}
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
                      <span className="text-sm tabular-nums">Embedding with Gemini · {Math.min(99, doc.progress)}%</span>
                    )}
                  </div>

                  {doc.status === "processing" && (
                    <div
                      className="nb-bar mt-3 h-2 w-full overflow-hidden"
                      style={{ borderRadius: brand.radius, backgroundColor: withAlpha(brand.neutralColor, 0.16) }}
                      role="progressbar"
                      aria-valuemin={0}
                      aria-valuemax={100}
                      aria-valuenow={Math.min(99, doc.progress)}
                      aria-label={"Indexing progress for " + doc.file_name}
                    >
                      <span
                        className="block h-full"
                        style={{ width: Math.min(99, doc.progress) + "%", backgroundColor: brand.accentColor }}
                      />
                    </div>
                  )}

                  {doc.status === "failed" && (
                    <p
                      className="mt-3 px-3 py-2 text-sm leading-relaxed"
                      style={{ borderRadius: brand.radius, backgroundColor: withAlpha(brand.primaryColor, 0.07), color: body }}
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
      <section aria-labelledby="rules-heading" className="mt-10 p-5" style={{ ...card, backgroundColor: withAlpha(brand.neutralColor, 0.06) }}>
        <h2 id="rules-heading" className="text-sm font-semibold uppercase tracking-wide" style={{ color: ink }}>
          How this board works
        </h2>
        <ul className="mt-3 grid gap-2 text-sm leading-relaxed sm:grid-cols-2">
          <li className="flex items-start gap-2">
            <Icons.Users className="mt-0.5 h-4 w-4 shrink-0" style={{ color: muted }} aria-hidden="true" />
            <span>No logins. Anyone with the link can upload or delete, and nothing records who did it.</span>
          </li>
          <li className="flex items-start gap-2">
            <Icons.AlertCircle className="mt-0.5 h-4 w-4 shrink-0" style={{ color: muted }} aria-hidden="true" />
            <span>Scanned, image-only PDFs fail: there is no OCR in this release.</span>
          </li>
          <li className="flex items-start gap-2">
            <Icons.Clock className="mt-0.5 h-4 w-4 shrink-0" style={{ color: muted }} aria-hidden="true" />
            <span className="tabular-nums">Uploads are rate-limited per connection to protect the Gemini quota.</span>
          </li>
          <li className="flex items-start gap-2">
            <Icons.Settings className="mt-0.5 h-4 w-4 shrink-0" style={{ color: muted }} aria-hidden="true" />
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
            style={{ borderRadius: brand.radius, backgroundColor: brand.backgroundColor, border: "1px solid " + line }}
          >
            <h2 id="delete-title" className="text-lg font-semibold" style={{ fontFamily: brand.fontHeading, color: ink }}>
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
              This board is shared with everyone who has the link. There is no undo and no copy kept.
            </p>
            <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
              <button
                type="button"
                ref={cancelRef}
                className="nb-focus px-4 py-2.5 text-sm font-semibold"
                style={{ borderRadius: brand.radius, border: "1px solid " + line, color: body, backgroundColor: "#FFFFFF" }}
                onClick={() => setConfirmDoc(null)}
              >
                Keep it
              </button>
              <button
                type="button"
                className="nb-focus px-4 py-2.5 text-sm font-semibold"
                style={{ borderRadius: brand.radius, backgroundColor: primaryStrong, color: "#FFFFFF" }}
                onClick={confirmDelete}
              >
                Delete permanently
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
