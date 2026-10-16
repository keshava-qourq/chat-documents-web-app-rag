// @ts-nocheck -- generated from the approved design under its JS runtime contract; not hand-written TypeScript.
/* eslint-disable @typescript-eslint/no-unused-vars */
import React from "react";

import * as UI from "@/lib/ui";
import { Icons } from "@/lib/icons";
import { brand } from "@/lib/brand";
import { useNavigate } from "@/lib/navigate";

const { Separator } = UI;

// Static operator documentation only. This screen calls no API endpoint —
// there is no /config or /status route in the contract — so nothing here is
// a live reading. Every value below is a description of what the delivered
// backend (FastAPI + Postgres/pgvector + MinIO) reads from its own
// environment, not a report of the running deployment's current state.

const ENV_VARS = [
  {
    env: "GEMINI_API_KEY",
    required: true,
    defaultText: "none — required",
    description:
      "Used for both embeddings and grounded chat generation. Read only on the server, at the moment it is needed. No endpoint in this app returns it, and this screen never renders it — not even masked.",
    where:
      "Create a key at aistudio.google.com/apikey and set it in your .env or host environment.",
  },
  {
    env: "DATABASE_URL",
    required: true,
    defaultText: "none — required",
    description:
      "Postgres connection string for the database holding documents, chunks, threads, messages and citations, with the pgvector extension enabled.",
    where:
      "docker-compose.yml starts a local Postgres 16 instance that matches the value in .env.example.",
  },
  {
    env: "MINIO_ENDPOINT",
    required: true,
    defaultText: "none — required",
    description:
      "Host:port of the S3-compatible MinIO instance original uploaded files are stored in.",
    where:
      "docker-compose.yml starts a local MinIO instance that matches the value in .env.example.",
  },
  {
    env: "MINIO_ACCESS_KEY",
    required: true,
    defaultText: "none — required",
    description: "Access key for the MinIO bucket above.",
    where: "Set to match the MINIO_ROOT_USER used by your MinIO instance.",
  },
  {
    env: "MINIO_SECRET_KEY",
    required: true,
    defaultText: "none — required",
    description: "Secret key for the MinIO bucket above.",
    where: "Set to match the MINIO_ROOT_PASSWORD used by your MinIO instance.",
  },
  {
    env: "MINIO_BUCKET",
    required: false,
    defaultText: "documents",
    description:
      "Bucket name original uploads are stored under. Created automatically on first use if it does not already exist.",
    where: "Optional — leave unset to use the default.",
  },
  {
    env: "DOCUMENT_CAP",
    required: false,
    defaultText: "200",
    description:
      "Total documents the shared library accepts before new uploads are refused. Deleting a document frees a slot immediately.",
    where: "Optional — leave unset to use the documented default.",
  },
  {
    env: "RATE_LIMIT_CHAT_PER_MIN",
    required: false,
    defaultText: "20",
    description: "Questions answered per IP per minute before the chat endpoint returns 429.",
    where: "Optional — leave unset to use the documented default.",
  },
  {
    env: "RATE_LIMIT_UPLOADS_PER_HOUR",
    required: false,
    defaultText: "10",
    description: "Uploads accepted per IP per hour before the upload endpoint returns 429.",
    where: "Optional — leave unset to use the documented default.",
  },
];

const RUN_STEPS = [
  {
    title: "Copy the environment file",
    body: "Copy .env.example to .env, then fill in GEMINI_API_KEY. The MinIO and Postgres values already match docker-compose.yml.",
    code: "cp .env.example .env\n# then edit .env and set GEMINI_API_KEY",
  },
  {
    title: "Start Postgres and MinIO",
    body: "Brings up Postgres (with pgvector) and MinIO, the two backing services the backend reads MINIO_ENDPOINT and DATABASE_URL for.",
    code: "docker compose up -d",
  },
  {
    title: "Install and run the backend",
    body: "Installs the FastAPI app's dependencies and starts it with live reload.",
    code: "cd backend\npip install -r requirements.txt\nuvicorn app.main:app --reload",
  },
  {
    title: "Install and run the frontend",
    body: "Starts the Vite dev server for this React app, talking to the backend above.",
    code: "cd frontend\nnpm install\nnpm run dev",
  },
];

const TROUBLE = [
  {
    q: "Chat answers end with an error instead of a response",
    a: 'If GEMINI_API_KEY is unset, the chat stream ends with the error "Gemini is not configured." — the exact text the backend sends. Set GEMINI_API_KEY in your environment and restart the backend process; no endpoint will ever echo the key back to confirm it.',
  },
  {
    q: "The key is set but every answer still fails",
    a: 'If the key is set but rejected or out of quota, Gemini calls are retried and then the backend sends "The answer generation service is unavailable." Check the key in Google AI Studio to confirm it has not been revoked, and that your Google Cloud project has not hit its quota.',
  },
  {
    q: "A document came back failed",
    a: "Open it in the document library and read the reason shown there verbatim — for example, a scanned PDF with no extractable text. Re-export it with a text layer and upload again.",
  },
  {
    q: "Uploads are refused",
    a: "Either the library is at DOCUMENT_CAP — delete a document and the slot is free immediately — or that IP has passed RATE_LIMIT_UPLOADS_PER_HOUR, which clears by itself once the window elapses.",
  },
];

export default function Screen() {
  const navigate = useNavigate();
  const [tab, setTab] = React.useState("local");
  const [copied, setCopied] = React.useState(null);

  const tabRefs = [React.useRef(null), React.useRef(null), React.useRef(null)];

  const tint = (hex, a) => {
    const h = hex.replace("#", "");
    const n = parseInt(
      h.length === 3
        ? h
            .split("")
            .map((c) => c + c)
            .join("")
        : h,
      16,
    );
    return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${a})`;
  };

  React.useEffect(() => {
    if (!copied) return;
    const t = setTimeout(() => setCopied(null), 1800);
    return () => clearTimeout(t);
  }, [copied]);

  const doCopy = (id, text) => {
    try {
      if (navigator.clipboard) navigator.clipboard.writeText(text);
    } catch (e) {
      /* clipboard unavailable in this frame; the block stays selectable */
    }
    setCopied(id);
  };

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
        {copied === id ? (
          <Icons.Check className="w-3.5 h-3.5" aria-hidden="true" />
        ) : (
          <Icons.FileText className="w-3.5 h-3.5" aria-hidden="true" />
        )}
        {copied === id ? "Copied" : "Copy"}
      </button>
    </div>
  );

  return (
    <div
      className="min-h-full"
      style={{
        backgroundColor: brand.backgroundColor,
        fontFamily: brand.fontBody,
        color: "#1c1917",
      }}
    >
      <style>{`
        @keyframes sdc-in { from { opacity: 0; transform: translateY(-4px); } to { opacity: 1; transform: none; } }
        .sdc-in { animation: sdc-in .22s ease-out both; }
        @media (prefers-reduced-motion: reduce) {
          .sdc-in { animation: none !important; }
        }
      `}</style>

      <div className="mx-auto max-w-5xl px-4 sm:px-6 lg:px-8 py-8 sm:py-10">
        {/* Header */}
        <header>
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
          <p
            className="mt-2 max-w-2xl text-[15px] leading-relaxed"
            style={{ color: brand.neutralColor }}
          >
            Static reference documentation for this install, not a live status page. This screen
            calls no API and polls nothing, so nothing below is a reading of the running deployment
            — it describes what the delivered backend reads from its own environment and how to run
            it.
          </p>
        </header>

        {/* Environment variables */}
        <section aria-labelledby="env-heading" className="mt-8">
          <h2
            id="env-heading"
            className="text-xl font-semibold"
            style={{ fontFamily: brand.fontHeading }}
          >
            Environment variables
          </h2>
          <p className="mt-1.5 text-sm max-w-2xl" style={{ color: brand.neutralColor }}>
            Every variable the backend reads, and the documented default it falls back to when
            unset.
          </p>
          <div style={card} className="mt-4 overflow-hidden">
            <ul>
              {ENV_VARS.map((v, i) => (
                <li
                  key={v.env}
                  className="px-5 sm:px-6 py-4"
                  style={{
                    borderTop: i === 0 ? "none" : `1px solid ${tint(brand.neutralColor, 0.16)}`,
                  }}
                >
                  <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                    <code
                      className="text-xs px-1.5 py-0.5 font-semibold"
                      style={{
                        color: brand.neutralColor,
                        backgroundColor: tint(brand.neutralColor, 0.1),
                        borderRadius: "0.25rem",
                      }}
                    >
                      {v.env}
                    </code>
                    <span
                      className="inline-flex items-center px-2 py-0.5 text-xs font-semibold"
                      style={{
                        color: v.required ? brand.primaryColor : brand.neutralColor,
                        backgroundColor: tint(
                          v.required ? brand.primaryColor : brand.neutralColor,
                          0.1,
                        ),
                        borderRadius: 999,
                      }}
                    >
                      {v.required ? "Required" : "Optional"}
                    </span>
                    <span
                      className="text-[13px]"
                      style={{ color: brand.neutralColor, fontVariantNumeric: "tabular-nums" }}
                    >
                      Default: {v.defaultText}
                    </span>
                  </div>
                  <p className="mt-2 text-sm leading-relaxed max-w-2xl">{v.description}</p>
                  <p className="mt-1 text-[13px] max-w-2xl" style={{ color: brand.neutralColor }}>
                    {v.where}
                  </p>
                </li>
              ))}
            </ul>
          </div>
          <div
            className="mt-4 flex items-start gap-2.5 px-4 py-3 text-sm max-w-2xl"
            style={{
              backgroundColor: tint(brand.neutralColor, 0.08),
              border: `1px solid ${tint(brand.neutralColor, 0.25)}`,
              borderRadius: brand.radius,
            }}
          >
            <Icons.X
              className="w-4 h-4 shrink-0 mt-0.5"
              aria-hidden="true"
              style={{ color: brand.primaryColor }}
            />
            <span>
              <strong className="font-semibold">GEMINI_API_KEY is never shown here.</strong> It is
              read server-side only, and no endpoint in this app returns it — so this screen has no
              value to display, masked or otherwise. Whoever holds the server or host environment
              can confirm it is set.
            </span>
          </div>
        </section>

        {/* Setup notes */}
        <section aria-labelledby="notes-heading" className="mt-10">
          <h2
            id="notes-heading"
            className="text-xl font-semibold"
            style={{ fontFamily: brand.fontHeading }}
          >
            Setup notes
          </h2>
          <p className="mt-1.5 text-sm max-w-2xl" style={{ color: brand.neutralColor }}>
            From a clean machine to a cited answer.
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
              <div
                id="panel-local"
                role="tabpanel"
                aria-labelledby="tab-local"
                tabIndex={-1}
                className="sdc-in"
              >
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
                        <h3
                          className="text-[15px] font-semibold"
                          style={{ fontFamily: brand.fontHeading }}
                        >
                          {s.title}
                        </h3>
                        <p
                          className="mt-1 text-sm leading-relaxed max-w-2xl"
                          style={{ color: brand.neutralColor }}
                        >
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
              <div
                id="panel-deploy"
                role="tabpanel"
                aria-labelledby="tab-deploy"
                tabIndex={-1}
                className="sdc-in"
              >
                <h3 className="text-[15px] font-semibold" style={{ fontFamily: brand.fontHeading }}>
                  Three processes: Postgres/pgvector, MinIO, and the FastAPI backend, plus a static
                  frontend build
                </h3>
                <p
                  className="mt-1.5 text-sm leading-relaxed max-w-2xl"
                  style={{ color: brand.neutralColor }}
                >
                  Sized for 5–25 people and a few hundred documents.
                </p>
                <ul className="mt-5 space-y-4 text-sm leading-relaxed max-w-2xl">
                  {[
                    [
                      "Set the same variables on the host",
                      "Copy them from your .env into the host's environment settings. Never commit the key and never expose it to the client bundle — every Gemini call, for answers and for embeddings, is made from the server.",
                    ],
                    [
                      "Run Postgres with pgvector and MinIO",
                      "Either via docker-compose.yml on the host, or managed equivalents. The database role needs permission to CREATE EXTENSION vector.",
                    ],
                    [
                      "Run the backend",
                      "Start uvicorn app.main:app behind a process manager (or a container orchestrator) after pip install -r requirements.txt.",
                    ],
                    [
                      "Build and serve the frontend",
                      "npm run build produces static files to serve from any static host or reverse proxy in front of the backend.",
                    ],
                    [
                      "Keep the URL private",
                      "There is no login and no password gate. Anyone who finds the link can read, upload and delete everything — the document cap and the per-IP limits are all that stand between a stranger and your Gemini quota.",
                    ],
                  ].map(([t, d]) => (
                    <li key={t} className="flex gap-3">
                      <Icons.Check
                        className="w-4 h-4 shrink-0 mt-1"
                        aria-hidden="true"
                        style={{ color: brand.accentColor }}
                      />
                      <span>
                        <strong className="font-semibold">{t}.</strong>{" "}
                        <span style={{ color: brand.neutralColor }}>{d}</span>
                      </span>
                    </li>
                  ))}
                </ul>
                <CodeBlock
                  id="deploy-cmd"
                  code={
                    "docker compose up -d\ncd backend && pip install -r requirements.txt && uvicorn app.main:app --host 0.0.0.0 --port 8000\ncd frontend && npm install && npm run build"
                  }
                />
              </div>
            )}

            {tab === "trouble" && (
              <div
                id="panel-trouble"
                role="tabpanel"
                aria-labelledby="tab-trouble"
                tabIndex={-1}
                className="sdc-in"
              >
                <dl className="space-y-6">
                  {TROUBLE.map((t) => (
                    <div key={t.q}>
                      <dt
                        className="text-[15px] font-semibold"
                        style={{ fontFamily: brand.fontHeading }}
                      >
                        {t.q}
                      </dt>
                      <dd
                        className="mt-1.5 text-sm leading-relaxed max-w-2xl"
                        style={{ color: brand.neutralColor }}
                      >
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
            No plans, no paywall and no usage billing anywhere in this app. Gemini usage for answers
            and embeddings is charged to the operator&apos;s own Google account — this app bills no
            one.
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
