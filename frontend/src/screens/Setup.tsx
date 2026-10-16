// @ts-nocheck -- generated from the approved design under its JS runtime contract; not hand-written TypeScript.
/* eslint-disable @typescript-eslint/no-unused-vars */
import React from "react";

import * as UI from "@/lib/ui";
import { Icons } from "@/lib/icons";
import { brand } from "@/lib/brand";
import { useNavigate } from "@/lib/navigate";

const { Input, Label, Separator } = UI;
const { Check, X, ChevronDown, Users, Settings, FileText, Clock, Upload, ArrowLeft, ArrowRight, AlertCircle, CheckCircle } = Icons;

const INITIAL_CHECKS = [
  {
    id: "key",
    env: "GEMINI_API_KEY",
    name: "Gemini API key",
    status: "ok",
    value: "Set on the server · accepted at 09:14 · ends ••••7f2a",
    detail:
      "The key was read from the server environment at boot and accepted by generateContent (gemini-2.5-flash). It is never written into a page, a bundle or an API response — the browser only receives finished answers.",
    where: "Set GEMINI_API_KEY in .env locally, or as an environment variable in your host's dashboard.",
  },
  {
    id: "embed",
    env: "GEMINI_EMBED_MODEL",
    name: "Embedding model",
    status: "attention",
    value: "text-embedding-004 · 3 rate-limit errors in the last hour",
    detail:
      "Gemini answered 429 Too Many Requests on 3 of 118 embedding calls since 08:20. Retries ran out for 2 documents, so they are marked failed in the library — no half-written chunks were left in the index. Raise the quota on your Google account, or slow the indexer with INDEXER_CONCURRENCY=1.",
    where: "Optional. Defaults to text-embedding-004 when unset.",
    action: { label: "Re-queue the 2 failed documents", id: "requeue" },
  },
  {
    id: "db",
    env: "DATABASE_URL",
    name: "Postgres and pgvector",
    status: "ok",
    value: "Connected · pgvector 0.7.4 · 1,842 chunks stored",
    detail:
      "Holds documents, chunks, threads, messages and citations. The pgvector extension is installed and the ivfflat index on chunks.embedding is present, so retrieval runs on the index rather than a sequential scan.",
    where: "postgres://user:password@host:5432/sharedlibrary — the role needs CREATE EXTENSION once.",
  },
  {
    id: "storage",
    env: "STORAGE_BUCKET",
    name: "Object storage",
    status: "ok",
    value: "shared-library · 184 MB of 5 GB used",
    detail:
      "Original uploads are written here under documents.storage_key. Deleting a document removes the stored file as well as its chunks, so storage does not drift away from the library.",
    where: "Any S3-compatible bucket. Also needs STORAGE_REGION, STORAGE_ACCESS_KEY and STORAGE_SECRET.",
  },
  {
    id: "cap",
    env: "DOCUMENT_CAP",
    name: "Document cap",
    status: "ok",
    value: "200 documents · 24 in the library now",
    detail:
      "Once the library is full, new uploads are refused with a message asking for an existing document to be deleted first. Deleting one frees the slot straight away — no restart.",
    where: "Documented default is 200 if DOCUMENT_CAP is unset.",
  },
  {
    id: "chatrl",
    env: "RATE_LIMIT_CHAT_PER_MIN",
    name: "Chat rate limit",
    status: "ok",
    value: "20 questions per IP per minute",
    detail:
      "Counted server-side per IP. Over the limit, the chat replies \"too many requests, try again shortly\" and makes no Gemini call at all, so a stranger with the link cannot spend your quota.",
    where: "Default 20. A 5–25 person team does not normally reach it.",
  },
  {
    id: "uploadrl",
    env: "RATE_LIMIT_UPLOADS_PER_HOUR",
    name: "Upload rate limit",
    status: "default",
    value: "Not set · using the documented default of 10 per IP per hour",
    detail:
      "Nothing is wrong — the app falls back to its documented default. Set the variable explicitly if you want the limit recorded in your own configuration rather than inherited from the code.",
    where: "Default 10. Rejected uploads store no file and embed nothing.",
  },
  {
    id: "access",
    env: "—",
    name: "Open access",
    status: "open",
    value: "No login, no shared password — anyone with the link has full access",
    detail:
      "This is the agreed model, not a misconfiguration. Every visitor can read, upload and delete every document and every thread, with no undo and no record of who did it. The rate limits and the document cap are the only protection. Keep the URL inside the team.",
    where: "There is no setting to turn this on or off in this release.",
  },
];

const RUN_STEPS = [
  {
    title: "Clone and install",
    body: "Node 20 or newer. The app and the background indexer run in one process — there is no queue service to start.",
    code: "git clone git@github.com:your-org/shared-docs-chat.git\ncd shared-docs-chat && npm install",
  },
  {
    title: "Write your .env",
    body: "Every value the app reads. Only the first one is secret, and it is only ever read on the server.",
    code:
      "GEMINI_API_KEY=AIza...            # from aistudio.google.com/apikey\nDATABASE_URL=postgres://app:pw@localhost:5432/sharedlibrary\nSTORAGE_BUCKET=shared-library\nSTORAGE_REGION=eu-west-1\nSTORAGE_ACCESS_KEY=...\nSTORAGE_SECRET=...\nDOCUMENT_CAP=200                  # default 200\nRATE_LIMIT_CHAT_PER_MIN=20        # default 20\nRATE_LIMIT_UPLOADS_PER_HOUR=10    # default 10",
  },
  {
    title: "Create the schema",
    body: "Creates documents, chunks, threads, messages and citations, enables pgvector and builds the embedding index.",
    code: "npm run db:push",
  },
  {
    title: "Start it",
    body: "App on :3000. Upload a PDF on the documents screen, wait for it to turn ready, then ask it something in chat.",
    code: "npm run dev",
  },
];

const TROUBLE = [
  {
    q: "The app starts, then every answer errors",
    a: "If GEMINI_API_KEY is missing or rejected, the server logs \"Configuration error: GEMINI_API_KEY is not set\" or \"...was rejected by Gemini (403)\" and refuses to call the API. Fix the key and restart — the error names the variable, so you are never guessing.",
  },
  {
    q: "A PDF came back as failed",
    a: "Open it in the library and read the reason. \"No extractable text found\" means it is a scan or an image-only export; this release has no OCR, so there is nothing to index. Re-export it with a text layer and upload again.",
  },
  {
    q: "Indexing stalls with 429s",
    a: "Gemini is rate-limiting the embedding calls. Set INDEXER_CONCURRENCY=1 or raise the quota on your Google account, then re-queue the failed documents from this screen.",
  },
  {
    q: "Uploads are refused",
    a: "Either the library is at DOCUMENT_CAP — delete a document and the slot is free immediately — or that IP has passed RATE_LIMIT_UPLOADS_PER_HOUR, which clears by itself when the window elapses.",
  },
];

export default function Screen() {
  const navigate = useNavigate();
  const [checks, setChecks] = React.useState(INITIAL_CHECKS);
  const [expanded, setExpanded] = React.useState("embed");
  const [onlyProblems, setOnlyProblems] = React.useState(false);
  const [running, setRunning] = React.useState(false);
  const [runCount, setRunCount] = React.useState(0);
  const [runError, setRunError] = React.useState(false);
  const [lastRead, setLastRead] = React.useState("09:14");
  const [notice, setNotice] = React.useState(null);
  const [tab, setTab] = React.useState("local");
  const [copied, setCopied] = React.useState(null);
  const [keyNote, setKeyNote] = React.useState(false);
  const [limits, setLimits] = React.useState({ cap: "200", chat: "20", upload: "" });
  const [limitError, setLimitError] = React.useState(null);

  const tabRefs = [React.useRef(null), React.useRef(null), React.useRef(null)];

  const tint = (hex, a) => {
    const h = hex.replace("#", "");
    const n = parseInt(h.length === 3 ? h.split("").map((c) => c + c).join("") : h, 16);
    return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${a})`;
  };

  React.useEffect(() => {
    if (!running) return;
    const t = setTimeout(() => {
      const failed = runCount === 2;
      setRunning(false);
      setRunError(failed);
      if (!failed) {
        setLastRead("just now");
        const problems = checks.filter((c) => c.status === "attention").length;
        const defaults = checks.filter((c) => c.status === "default").length;
        setNotice({
          tone: "ok",
          text:
            `Re-ran ${checks.length} checks · ${checks.length - problems - defaults} passed` +
            (problems ? ` · ${problems} need attention` : "") +
            (defaults ? ` · ${defaults} using a documented default` : ""),
        });
      }
    }, 1200);
    return () => clearTimeout(t);
  }, [running]);

  React.useEffect(() => {
    if (!copied) return;
    const t = setTimeout(() => setCopied(null), 1800);
    return () => clearTimeout(t);
  }, [copied]);

  const runChecks = () => {
    setRunError(false);
    setNotice(null);
    setRunCount((n) => n + 1);
    setRunning(true);
  };

  const doCopy = (id, text) => {
    try {
      if (navigator.clipboard) navigator.clipboard.writeText(text);
    } catch (e) {
      /* clipboard unavailable in this frame; the block stays selectable */
    }
    setCopied(id);
  };

  const requeue = () => {
    setChecks((cs) =>
      cs.map((c) =>
        c.id === "embed"
          ? {
              ...c,
              status: "ok",
              value: "text-embedding-004 · 2 documents re-queued at 09:41",
              detail:
                "The 2 failed documents were put back on the indexer with a slower concurrency. They return to processing in the library and reach ready or failed without this screen being open.",
            }
          : c
      )
    );
    setNotice({ tone: "ok", text: "2 documents re-queued. Watch them turn ready on the documents screen." });
  };

  const saveLimits = (e) => {
    e.preventDefault();
    const cap = parseInt(limits.cap, 10);
    const chat = parseInt(limits.chat, 10);
    const upload = limits.upload === "" ? null : parseInt(limits.upload, 10);
    if (!Number.isInteger(cap) || cap < 1 || cap > 2000) {
      setLimitError("The document cap must be a whole number between 1 and 2000. Your other values are untouched.");
      return;
    }
    if (!Number.isInteger(chat) || chat < 1) {
      setLimitError("Chat requests per IP must be at least 1 — set it high rather than removing it.");
      return;
    }
    if (upload !== null && (!Number.isInteger(upload) || upload < 1)) {
      setLimitError("Uploads per IP must be a whole number, or left blank to keep the default of 10.");
      return;
    }
    setLimitError(null);
    setChecks((cs) =>
      cs.map((c) => {
        if (c.id === "cap") return { ...c, value: `${cap} documents · 24 in the library now` };
        if (c.id === "chatrl") return { ...c, value: `${chat} questions per IP per minute` };
        if (c.id === "uploadrl")
          return upload === null
            ? c
            : {
                ...c,
                status: "ok",
                value: `${upload} uploads per IP per hour`,
                detail:
                  "Set explicitly in the running config. Rejected uploads store no file and embed nothing, and the window clears without any manual step.",
              };
        return c;
      })
    );
    setNotice({
      tone: "ok",
      text:
        upload === null
          ? "Limits saved to the running config. No restart needed."
          : "Limits saved to the running config, including the upload limit. No restart needed.",
    });
  };

  const statusMeta = {
    ok: { label: "Ready", color: brand.accentColor, Icon: Icons.CheckCircle },
    attention: { label: "Needs attention", color: brand.primaryColor, Icon: Icons.AlertCircle },
    default: { label: "Using default", color: brand.neutralColor, Icon: Icons.Settings },
    open: { label: "By design", color: brand.neutralColor, Icon: Icons.Users },
  };

  const visible = onlyProblems ? checks.filter((c) => c.status === "attention" || c.status === "default") : checks;
  const attentionCount = checks.filter((c) => c.status === "attention").length;
  const defaultCount = checks.filter((c) => c.status === "default").length;

  const card = {
    backgroundColor: "#ffffff",
    borderRadius: brand.radius,
    border: `1px solid ${tint(brand.neutralColor, 0.22)}`,
  };
  const codeBox = {
    backgroundColor: brand.backgroundColor,
    border: `1px solid ${tint(brand.neutralColor, 0.25)}`,
    borderRadius: brand.radius,
  };

  const headline =
    attentionCount > 0
      ? `${attentionCount} setting needs attention`
      : defaultCount > 0
      ? `Everything is wired up · ${defaultCount} using a documented default`
      : "Everything is wired up";

  const CodeBlock = ({ id, code }) => (
    <div className="relative mt-3">
      <pre
        className="overflow-x-auto p-3 pr-24 text-[13px] leading-6 whitespace-pre"
        style={{ ...codeBox, fontVariantNumeric: "tabular-nums", color: brand.neutralColor }}
      >
        <code style={{ color: "#1c1917" }}>{code}</code>
      </pre>
      <button
        type="button"
        onClick={() => doCopy(id, code)}
        className="absolute top-2 right-2 inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-semibold focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 transition-colors"
        style={{
          borderRadius: brand.radius,
          border: `1px solid ${tint(brand.neutralColor, 0.3)}`,
          backgroundColor: "#ffffff",
          color: copied === id ? brand.accentColor : brand.neutralColor,
        }}
      >
        {copied === id ? <Icons.Check className="w-3.5 h-3.5" aria-hidden="true" /> : <Icons.FileText className="w-3.5 h-3.5" aria-hidden="true" />}
        {copied === id ? "Copied" : "Copy"}
      </button>
    </div>
  );

  return (
    <div
      className="min-h-full"
      style={{ backgroundColor: brand.backgroundColor, fontFamily: brand.fontBody, color: "#1c1917" }}
    >
      <style>{`
        @keyframes sdc-in { from { opacity: 0; transform: translateY(-4px); } to { opacity: 1; transform: none; } }
        @keyframes sdc-pulse { 0%,100% { opacity: .45 } 50% { opacity: 1 } }
        .sdc-in { animation: sdc-in .22s ease-out both; }
        .sdc-pulse { animation: sdc-pulse 1.1s ease-in-out infinite; }
        @media (prefers-reduced-motion: reduce) {
          .sdc-in, .sdc-pulse { animation: none !important; }
        }
      `}</style>

      <div className="mx-auto max-w-5xl px-4 sm:px-6 lg:px-8 py-8 sm:py-10">
        {/* Header */}
        <header className="flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p
              className="text-xs font-semibold uppercase tracking-[0.14em] mb-2"
              style={{ color: brand.neutralColor }}
            >
              Operator
            </p>
            <h1
              className="text-3xl sm:text-4xl font-bold tracking-tight"
              style={{ fontFamily: brand.fontHeading }}
            >
              Setup &amp; status
            </h1>
            <p className="mt-2 max-w-xl text-[15px] leading-relaxed" style={{ color: brand.neutralColor }}>
              What this install is reading from its environment, and how to run it. The Gemini key is checked on the
              server — it never reaches this page.
            </p>
          </div>
          <div className="flex items-center gap-3 shrink-0">
            <span
              className="hidden sm:inline-flex items-center gap-1.5 text-[13px]"
              style={{ color: brand.neutralColor, fontVariantNumeric: "tabular-nums" }}
            >
              <Icons.Clock className="w-4 h-4" aria-hidden="true" />
              Status read {lastRead}
            </span>
            <button
              type="button"
              onClick={runChecks}
              disabled={running}
              className="inline-flex items-center gap-2 px-4 py-2.5 text-sm font-semibold text-white transition-opacity focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 disabled:opacity-70"
              style={{ backgroundColor: brand.primaryColor, borderRadius: brand.radius }}
            >
              <Icons.ArrowRight className={running ? "w-4 h-4 sdc-pulse" : "w-4 h-4"} aria-hidden="true" />
              {running ? "Running checks…" : "Run checks again"}
            </button>
          </div>
        </header>

        {/* Stale / notice / error strip */}
        <div className="mt-6 space-y-3" aria-live="polite">
          {lastRead !== "just now" && !runError && (
            <p
              className="flex items-center gap-2 text-[13px] px-3 py-2"
              style={{
                color: brand.neutralColor,
                backgroundColor: tint(brand.neutralColor, 0.08),
                borderRadius: brand.radius,
              }}
            >
              <Icons.Clock className="w-4 h-4 shrink-0" aria-hidden="true" />
              Live polling is off on this screen. These values were read at 09:14 — run the checks for a fresh read.
            </p>
          )}
          {runError && (
            <div
              className="sdc-in flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between px-4 py-3"
              style={{
                backgroundColor: tint(brand.primaryColor, 0.09),
                border: `1px solid ${tint(brand.primaryColor, 0.35)}`,
                borderRadius: brand.radius,
              }}
            >
              <p className="flex items-start gap-2.5 text-sm" style={{ color: brand.primaryColor }}>
                <Icons.AlertCircle className="w-5 h-5 shrink-0 mt-px" aria-hidden="true" />
                <span>
                  <strong className="font-semibold">The check run didn&apos;t finish.</strong>{" "}
                  <span style={{ color: "#1c1917" }}>
                    /healthz didn&apos;t answer within 5 seconds, so nothing below was refreshed. The values shown are
                    still the ones read at 09:14.
                  </span>
                </span>
              </p>
              <button
                type="button"
                onClick={runChecks}
                className="self-start shrink-0 px-3 py-2 text-sm font-semibold focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2"
                style={{
                  borderRadius: brand.radius,
                  backgroundColor: "#ffffff",
                  border: `1px solid ${tint(brand.primaryColor, 0.45)}`,
                  color: brand.primaryColor,
                }}
              >
                Try the check again
              </button>
            </div>
          )}
          {notice && !runError && (
            <p
              className="sdc-in flex items-center gap-2 text-sm px-4 py-3"
              style={{
                backgroundColor: tint(brand.accentColor, 0.08),
                border: `1px solid ${tint(brand.accentColor, 0.3)}`,
                borderRadius: brand.radius,
                color: brand.accentColor,
                fontVariantNumeric: "tabular-nums",
              }}
            >
              <Icons.CheckCircle className="w-4 h-4 shrink-0" aria-hidden="true" />
              {notice.text}
            </p>
          )}
        </div>

        {/* Focal: configuration checklist */}
        <section aria-labelledby="checks-heading" className="mt-6">
          <div style={card} className="overflow-hidden">
            <div className="flex flex-col gap-4 px-5 sm:px-6 pt-5 sm:pt-6 pb-4 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <h2 id="checks-heading" className="text-xl font-semibold" style={{ fontFamily: brand.fontHeading }}>
                  {headline}
                </h2>
                <p className="mt-1 text-sm" style={{ color: brand.neutralColor }}>
                  Eight environment checks, read on the server. Open a row for the reason and where to set it.
                </p>
              </div>
              <button
                type="button"
                role="switch"
                aria-checked={onlyProblems}
                onClick={() => setOnlyProblems((v) => !v)}
                className="inline-flex items-center gap-3 shrink-0 text-sm font-medium focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 rounded"
                style={{ color: "#1c1917" }}
              >
                <span
                  aria-hidden="true"
                  className="relative inline-block w-10 h-6 transition-colors"
                  style={{
                    borderRadius: 999,
                    backgroundColor: onlyProblems ? brand.primaryColor : tint(brand.neutralColor, 0.3),
                  }}
                >
                  <span
                    className="absolute top-0.5 left-0.5 w-5 h-5 bg-white transition-transform"
                    style={{ borderRadius: 999, transform: onlyProblems ? "translateX(16px)" : "none" }}
                  />
                </span>
                Only what needs attention
              </button>
            </div>

            <Separator />

            {visible.length === 0 ? (
              <div className="px-6 py-14 text-center">
                <Icons.CheckCircle
                  className="w-10 h-10 mx-auto"
                  aria-hidden="true"
                  style={{ color: brand.accentColor }}
                />
                <h3 className="mt-4 text-lg font-semibold" style={{ fontFamily: brand.fontHeading }}>
                  Nothing needs attention
                </h3>
                <p className="mt-1.5 text-sm max-w-sm mx-auto" style={{ color: brand.neutralColor }}>
                  All {checks.length} checks passed and every limit is set explicitly. Turn the filter off to read the
                  full configuration.
                </p>
                <button
                  type="button"
                  onClick={() => setOnlyProblems(false)}
                  className="mt-5 px-4 py-2.5 text-sm font-semibold text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2"
                  style={{ backgroundColor: brand.primaryColor, borderRadius: brand.radius }}
                >
                  Show all checks
                </button>
              </div>
            ) : (
              <ul>
                {visible.map((c, i) => {
                  const meta = statusMeta[c.status];
                  const open = expanded === c.id;
                  return (
                    <li
                      key={c.id}
                      style={{ borderTop: i === 0 ? "none" : `1px solid ${tint(brand.neutralColor, 0.16)}` }}
                    >
                      <h3>
                        <button
                          type="button"
                          aria-expanded={open}
                          aria-controls={`detail-${c.id}`}
                          onClick={() => setExpanded(open ? null : c.id)}
                          className="w-full text-left px-5 sm:px-6 py-4 flex items-start gap-4 transition-colors hover:bg-black/[0.02] focus:outline-none focus-visible:ring-2 focus-visible:ring-inset"
                        >
                          <meta.Icon
                            className={running ? "w-5 h-5 shrink-0 mt-0.5 sdc-pulse" : "w-5 h-5 shrink-0 mt-0.5"}
                            aria-hidden="true"
                            style={{ color: meta.color }}
                          />
                          <span className="min-w-0 flex-1">
                            <span className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                              <span className="text-[15px] font-semibold">{c.name}</span>
                              <code
                                className="text-xs px-1.5 py-0.5"
                                style={{
                                  color: brand.neutralColor,
                                  backgroundColor: tint(brand.neutralColor, 0.1),
                                  borderRadius: "0.25rem",
                                }}
                              >
                                {c.env}
                              </code>
                            </span>
                            <span
                              className="mt-1 block text-sm break-words"
                              style={{ color: brand.neutralColor, fontVariantNumeric: "tabular-nums" }}
                            >
                              {running ? "Checking…" : c.value}
                            </span>
                          </span>
                          <span
                            className="hidden sm:inline-flex items-center gap-1.5 shrink-0 px-2.5 py-1 text-xs font-semibold"
                            style={{
                              color: meta.color,
                              backgroundColor: tint(meta.color, 0.1),
                              borderRadius: 999,
                            }}
                          >
                            {meta.label}
                          </span>
                          <Icons.ChevronDown
                            className="w-5 h-5 shrink-0 mt-0.5 transition-transform"
                            aria-hidden="true"
                            style={{ color: brand.neutralColor, transform: open ? "rotate(180deg)" : "none" }}
                          />
                        </button>
                      </h3>
                      {open && (
                        <div id={`detail-${c.id}`} className="sdc-in px-5 sm:px-6 pb-5 sm:pl-[3.75rem]">
                          <p className="text-sm leading-relaxed max-w-2xl">{c.detail}</p>
                          <p className="mt-2 text-[13px] max-w-2xl" style={{ color: brand.neutralColor }}>
                            {c.where}
                          </p>
                          <span
                            className="sm:hidden mt-3 inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-semibold"
                            style={{ color: meta.color, backgroundColor: tint(meta.color, 0.1), borderRadius: 999 }}
                          >
                            {meta.label}
                          </span>
                          <div className="mt-4 flex flex-wrap gap-2">
                            {c.action && (
                              <button
                                type="button"
                                onClick={requeue}
                                className="px-3.5 py-2 text-sm font-semibold text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2"
                                style={{ backgroundColor: brand.primaryColor, borderRadius: brand.radius }}
                              >
                                {c.action.label}
                              </button>
                            )}
                            {(c.id === "embed" || c.id === "cap" || c.id === "storage") && (
                              <button
                                type="button"
                                onClick={() => navigate("documents")}
                                className="px-3.5 py-2 text-sm font-semibold focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2"
                                style={{
                                  borderRadius: brand.radius,
                                  border: `1px solid ${tint(brand.neutralColor, 0.3)}`,
                                  color: brand.accentColor,
                                  backgroundColor: "#ffffff",
                                }}
                              >
                                Open the document library
                              </button>
                            )}
                            {c.id === "key" && (
                              <button
                                type="button"
                                onClick={() => setKeyNote(true)}
                                className="px-3.5 py-2 text-sm font-semibold focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2"
                                style={{
                                  borderRadius: brand.radius,
                                  border: `1px solid ${tint(brand.neutralColor, 0.3)}`,
                                  color: brand.accentColor,
                                  backgroundColor: "#ffffff",
                                }}
                              >
                                Show the full key
                              </button>
                            )}
                          </div>
                          {c.id === "key" && keyNote && (
                            <div
                              className="sdc-in mt-3 flex items-start gap-2.5 px-3.5 py-3 text-sm max-w-2xl"
                              style={{
                                backgroundColor: tint(brand.neutralColor, 0.08),
                                border: `1px solid ${tint(brand.neutralColor, 0.25)}`,
                                borderRadius: brand.radius,
                              }}
                            >
                              <Icons.X className="w-4 h-4 shrink-0 mt-0.5" aria-hidden="true" style={{ color: brand.primaryColor }} />
                              <span>
                                <strong className="font-semibold">Not from here.</strong> No endpoint in this app returns
                                the key, so no screen can display it. Whoever holds the server or host account can read it
                                from the environment — ask them, or mint a fresh key in Google AI Studio and replace it.
                                <button
                                  type="button"
                                  onClick={() => setKeyNote(false)}
                                  className="ml-2 underline font-semibold focus:outline-none focus-visible:ring-2 rounded"
                                  style={{ color: brand.accentColor }}
                                >
                                  Hide
                                </button>
                              </span>
                            </div>
                          )}
                        </div>
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </section>

        {/* Secondary row: live numbers + limits form */}
        <div className="mt-8 grid gap-6 lg:grid-cols-5">
          <section aria-labelledby="numbers-heading" className="lg:col-span-2">
            <h2 id="numbers-heading" className="text-sm font-semibold uppercase tracking-[0.12em]" style={{ color: brand.neutralColor }}>
              What is in the workspace
            </h2>
            <dl className="mt-3 space-y-3">
              {[
                { k: "Documents in the library", v: "24 / " + limits.cap, s: "22 ready · 2 failed" },
                { k: "Indexed chunks", v: "1,842", s: "across 22 ready documents" },
                { k: "Shared threads", v: "37", s: "last active today, 09:28" },
              ].map((m) => (
                <div key={m.k} className="px-4 py-3.5" style={card}>
                  <dt className="text-[13px]" style={{ color: brand.neutralColor }}>
                    {m.k}
                  </dt>
                  <dd>
                    <span className="block text-2xl font-semibold" style={{ fontVariantNumeric: "tabular-nums" }}>
                      {m.v}
                    </span>
                    <span className="block text-[13px] mt-0.5" style={{ color: brand.neutralColor }}>
                      {m.s}
                    </span>
                  </dd>
                </div>
              ))}
            </dl>
          </section>

          <section aria-labelledby="limits-heading" className="lg:col-span-3">
            <h2 id="limits-heading" className="text-sm font-semibold uppercase tracking-[0.12em]" style={{ color: brand.neutralColor }}>
              Guardrails
            </h2>
            <form onSubmit={saveLimits} className="mt-3 px-5 py-5" style={card} noValidate>
              <p className="text-sm leading-relaxed" style={{ color: brand.neutralColor }}>
                The only protection on an open link. Saving writes to the running config — no restart, and the new
                values apply to the next request.
              </p>
              <div className="mt-4 grid gap-4 sm:grid-cols-3">
                <div>
                  <Label htmlFor="cap">Document cap</Label>
                  <Input
                    id="cap"
                    type="number"
                    inputMode="numeric"
                    value={limits.cap}
                    onChange={(e) => setLimits({ ...limits, cap: e.target.value })}
                    style={{ fontVariantNumeric: "tabular-nums" }}
                  />
                  <p className="mt-1 text-xs" style={{ color: brand.neutralColor }}>
                    Total files stored
                  </p>
                </div>
                <div>
                  <Label htmlFor="chat">Chat per IP / min</Label>
                  <Input
                    id="chat"
                    type="number"
                    inputMode="numeric"
                    value={limits.chat}
                    onChange={(e) => setLimits({ ...limits, chat: e.target.value })}
                    style={{ fontVariantNumeric: "tabular-nums" }}
                  />
                  <p className="mt-1 text-xs" style={{ color: brand.neutralColor }}>
                    Questions answered
                  </p>
                </div>
                <div>
                  <Label htmlFor="upload">Uploads per IP / hour</Label>
                  <Input
                    id="upload"
                    type="number"
                    inputMode="numeric"
                    placeholder="10"
                    value={limits.upload}
                    onChange={(e) => setLimits({ ...limits, upload: e.target.value })}
                    style={{ fontVariantNumeric: "tabular-nums" }}
                  />
                  <p className="mt-1 text-xs" style={{ color: brand.neutralColor }}>
                    Blank keeps the default
                  </p>
                </div>
              </div>
              {limitError && (
                <p
                  className="sdc-in mt-4 flex items-start gap-2 text-sm px-3.5 py-2.5"
                  style={{
                    color: brand.primaryColor,
                    backgroundColor: tint(brand.primaryColor, 0.09),
                    borderRadius: brand.radius,
                  }}
                  role="alert"
                >
                  <Icons.AlertCircle className="w-4 h-4 shrink-0 mt-0.5" aria-hidden="true" />
                  {limitError}
                </p>
              )}
              <div className="mt-5 flex items-center gap-3">
                <button
                  type="submit"
                  className="px-4 py-2.5 text-sm font-semibold text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2"
                  style={{ backgroundColor: brand.primaryColor, borderRadius: brand.radius }}
                >
                  Save guardrails
                </button>
                <span className="text-[13px]" style={{ color: brand.neutralColor }}>
                  Applies to every visitor on the link.
                </span>
              </div>
            </form>
          </section>
        </div>

        {/* Setup notes */}
        <section aria-labelledby="notes-heading" className="mt-10">
          <h2 id="notes-heading" className="text-xl font-semibold" style={{ fontFamily: brand.fontHeading }}>
            Setup notes
          </h2>
          <p className="mt-1.5 text-sm max-w-2xl" style={{ color: brand.neutralColor }}>
            From a clean machine to a cited answer. Four steps, one process, one key.
          </p>

          <div
            role="tablist"
            aria-label="Setup notes sections"
            className="mt-5 flex flex-wrap gap-2"
            onKeyDown={(e) => {
              const ids = ["local", "deploy", "trouble"];
              const i = ids.indexOf(tab);
              if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
                e.preventDefault();
                const next = (i + (e.key === "ArrowRight" ? 1 : ids.length - 1)) % ids.length;
                setTab(ids[next]);
                const r = tabRefs[next].current;
                if (r) r.focus();
              }
            }}
          >
            {[
              { id: "local", label: "Run it locally" },
              { id: "deploy", label: "Deploy it" },
              { id: "trouble", label: "When it goes wrong" },
            ].map((t, idx) => {
              const active = tab === t.id;
              return (
                <button
                  key={t.id}
                  ref={tabRefs[idx]}
                  role="tab"
                  type="button"
                  id={`tab-${t.id}`}
                  aria-selected={active}
                  aria-controls={`panel-${t.id}`}
                  tabIndex={active ? 0 : -1}
                  onClick={() => setTab(t.id)}
                  className="px-4 py-2.5 text-sm font-semibold transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2"
                  style={{
                    borderRadius: brand.radius,
                    backgroundColor: active ? brand.primaryColor : "#ffffff",
                    color: active ? "#ffffff" : brand.neutralColor,
                    border: `1px solid ${active ? brand.primaryColor : tint(brand.neutralColor, 0.26)}`,
                  }}
                >
                  {t.label}
                </button>
              );
            })}
          </div>

          <div className="mt-4 px-5 sm:px-6 py-6" style={card}>
            {tab === "local" && (
              <div id="panel-local" role="tabpanel" aria-labelledby="tab-local" tabIndex={-1} className="sdc-in">
                <ol className="space-y-7">
                  {RUN_STEPS.map((s, i) => (
                    <li key={s.title} className="flex gap-4">
                      <span
                        aria-hidden="true"
                        className="shrink-0 inline-flex items-center justify-center w-7 h-7 text-sm font-bold"
                        style={{
                          borderRadius: 999,
                          backgroundColor: tint(brand.accentColor, 0.12),
                          color: brand.accentColor,
                          fontVariantNumeric: "tabular-nums",
                        }}
                      >
                        {i + 1}
                      </span>
                      <div className="min-w-0 flex-1">
                        <h3 className="text-[15px] font-semibold" style={{ fontFamily: brand.fontHeading }}>
                          {s.title}
                        </h3>
                        <p className="mt-1 text-sm leading-relaxed max-w-2xl" style={{ color: brand.neutralColor }}>
                          {s.body}
                        </p>
                        <CodeBlock id={`local-${i}`} code={s.code} />
                      </div>
                    </li>
                  ))}
                </ol>
              </div>
            )}

            {tab === "deploy" && (
              <div id="panel-deploy" role="tabpanel" aria-labelledby="tab-deploy" tabIndex={-1} className="sdc-in">
                <h3 className="text-[15px] font-semibold" style={{ fontFamily: brand.fontHeading }}>
                  One process, one key, no queue service
                </h3>
                <p className="mt-1.5 text-sm leading-relaxed max-w-2xl" style={{ color: brand.neutralColor }}>
                  The indexer runs inside the web process, so any host that can run a long-lived Node service will do.
                  Sized for 5–25 people and a few hundred documents.
                </p>
                <ul className="mt-5 space-y-4 text-sm leading-relaxed max-w-2xl">
                  {[
                    ["Set the same variables on the host", "Copy them from your .env into the host's environment settings. Never commit the key and never expose it to the client bundle — all Gemini calls for answers and embeddings are made from the server."],
                    ["Point at managed Postgres with pgvector", "Run npm run db:push once against the production database. The role needs permission to CREATE EXTENSION vector."],
                    ["Give it a bucket", "Originals live in object storage, chunks and embeddings in Postgres. A delete removes both, so nothing is orphaned."],
                    ["Keep the URL private", "There is no login and no password gate. Anyone who finds the link can read, upload and delete everything — the document cap and the per-IP limits are all that stand between a stranger and your Gemini quota."],
                  ].map(([t, d]) => (
                    <li key={t} className="flex gap-3">
                      <Icons.Check className="w-4 h-4 shrink-0 mt-1" aria-hidden="true" style={{ color: brand.accentColor }} />
                      <span>
                        <strong className="font-semibold">{t}.</strong> <span style={{ color: brand.neutralColor }}>{d}</span>
                      </span>
                    </li>
                  ))}
                </ul>
                <CodeBlock id="deploy-cmd" code={"npm run build\nnpm run db:push\nnpm start        # serves the app and runs the indexer"} />
              </div>
            )}

            {tab === "trouble" && (
              <div id="panel-trouble" role="tabpanel" aria-labelledby="tab-trouble" tabIndex={-1} className="sdc-in">
                <dl className="space-y-6">
                  {TROUBLE.map((t) => (
                    <div key={t.q}>
                      <dt className="text-[15px] font-semibold" style={{ fontFamily: brand.fontHeading }}>
                        {t.q}
                      </dt>
                      <dd className="mt-1.5 text-sm leading-relaxed max-w-2xl" style={{ color: brand.neutralColor }}>
                        {t.a}
                      </dd>
                    </div>
                  ))}
                </dl>
              </div>
            )}
          </div>
        </section>

        {/* Footer */}
        <footer className="mt-10 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-[13px] leading-relaxed max-w-md" style={{ color: brand.neutralColor }}>
            No plans, no paywall and no usage billing anywhere in this app. Gemini usage for answers and embeddings is
            charged to the operator&apos;s own Google account.
          </p>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => navigate("documents")}
              className="inline-flex items-center gap-2 px-3.5 py-2.5 text-sm font-semibold focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2"
              style={{
                borderRadius: brand.radius,
                backgroundColor: "#ffffff",
                border: `1px solid ${tint(brand.neutralColor, 0.3)}`,
                color: brand.accentColor,
              }}
            >
              <Icons.Upload className="w-4 h-4" aria-hidden="true" />
              Documents
            </button>
            <button
              type="button"
              onClick={() => navigate("chat")}
              className="inline-flex items-center gap-2 px-3.5 py-2.5 text-sm font-semibold focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2"
              style={{
                borderRadius: brand.radius,
                backgroundColor: "#ffffff",
                border: `1px solid ${tint(brand.neutralColor, 0.3)}`,
                color: brand.accentColor,
              }}
            >
              <Icons.ArrowRight className="w-4 h-4" aria-hidden="true" />
              Ask a question
            </button>
          </div>
        </footer>
      </div>
    </div>
  );
}
