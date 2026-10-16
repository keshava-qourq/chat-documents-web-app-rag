// @ts-nocheck -- generated from the approved design under its JS runtime contract; not hand-written TypeScript.
/* eslint-disable @typescript-eslint/no-unused-vars */
import React from "react";

import * as UI from "@/lib/ui";
import { Icons } from "@/lib/icons";
import { brand } from "@/lib/brand";
import { useNavigate } from "@/lib/navigate";

const { Button, Input, Textarea } = UI;
const { Plus, Search, Check, X, ChevronRight, ChevronDown, Users, FileText, Calendar, Clock, Trash, Edit, ArrowRight, AlertCircle, CheckCircle } = Icons;

const LIBRARY = { ready: 12, processing: 2, failed: 1, cap: 50 };

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

const STARTERS = [
  "What's the per-head limit for client dinners?",
  "Which laptops are approved for contractors?",
  "How much parental leave top-up do Dutch staff get?",
  "When does the Berlin office close over Christmas?",
];

const SEED_THREADS = [
  {
    id: "t-1",
    title: "Parental leave top-up for Dutch staff",
    created_at: "2026-10-16T11:31:00",
    last_active_at: "2026-10-16T11:42:00",
    messages: [
      {
        id: "m-1",
        role: "user",
        author: "A visitor",
        status: "complete",
        created_at: "2026-10-16T11:31:00",
        content: "How much does the company top up parental leave for staff in the Netherlands?",
      },
      {
        id: "m-2",
        role: "assistant",
        status: "complete",
        created_at: "2026-10-16T11:32:00",
        content:
          "Dutch staff receive the statutory parental benefit — 70% of salary for 9 of the 26 weeks, paid by UWV — and the company tops that up to 100% of base salary for those 9 weeks.\n\nThe top-up runs through normal payroll and does not apply to the remaining 17 unpaid weeks. Staff must give People Ops four weeks' notice before the first day of leave for the top-up to be processed in time.",
        citations: [
          {
            id: "c-1",
            document_name: "People-Handbook-2026.pdf",
            source_location: "page 34",
            excerpt:
              "Employees based in the Netherlands are entitled to 26 weeks of parental leave per child before the child's eighth birthday. For nine of those weeks UWV pays 70% of daily wages; Section 6 of this handbook commits the company to topping this payment up to 100% of base salary. The remaining seventeen weeks are unpaid.",
          },
          {
            id: "c-2",
            document_name: "Benefits-NL-2026.docx",
            source_location: 'section 4.1 "Leave top-ups"',
            excerpt:
              "Top-ups are processed through the regular monthly payroll run and appear as a separate line item (code PLT-100). People Ops requires four weeks' notice ahead of the first day of leave; requests filed later are paid in the following month's run.",
          },
        ],
      },
      {
        id: "m-3",
        role: "user",
        author: "A visitor",
        status: "complete",
        created_at: "2026-10-16T11:41:00",
        content: "And what about the Berlin office?",
      },
      {
        id: "m-4",
        role: "assistant",
        status: "complete",
        created_at: "2026-10-16T11:42:00",
        content:
          "For Berlin, the handbook confirms Elterngeld is handled by the state and that the company adds a one-off €1,200 \"new family\" payment in the first payroll run after the birth is registered.\n\nWhat the documents don't cover: whether Berlin staff also get a salary top-up during Elternzeit the way Dutch staff do. There is nothing about a German top-up in any uploaded file, so I can't answer that part.",
        citations: [
          {
            id: "c-3",
            document_name: "People-Handbook-2026.pdf",
            source_location: "page 35",
            excerpt:
              "German employees apply for Elterngeld directly through their local Elterngeldstelle. The company does not administer the claim. A one-off new family payment of €1,200 gross is made in the first payroll run following registration of the birth.",
          },
        ],
      },
    ],
  },
  {
    id: "t-2",
    title: "Approved laptops for contractors",
    created_at: "2026-10-15T16:02:00",
    last_active_at: "2026-10-15T16:08:00",
    messages: [
      {
        id: "m-5",
        role: "user",
        author: "A visitor",
        status: "complete",
        created_at: "2026-10-15T16:02:00",
        content: "Which laptops are contractors allowed to use on our projects?",
      },
      {
        id: "m-6",
        role: "assistant",
        status: "complete",
        created_at: "2026-10-15T16:08:00",
        content:
          "Contractors can either take a company-issued MacBook Air (M3, 16 GB) or bring their own device if it meets the baseline: full-disk encryption on, operating system within one major version of current, screen lock after five minutes, and the MDM agent enrolled before any shared-drive access is granted.\n\nWindows machines are allowed under the same baseline. Linux is not supported by the MDM agent, so Linux devices can't be enrolled.",
        citations: [
          {
            id: "c-4",
            document_name: "Security-Baseline.md",
            source_location: 'section 4.2 "Contractor devices"',
            excerpt:
              "Bring-your-own devices are permitted for contractors provided all four baseline controls are verifiable at enrolment: FileVault or BitLocker enabled, OS no more than one major version behind, automatic lock at five minutes, and successful MDM check-in. Linux endpoints cannot be enrolled and are therefore out of scope for shared-drive access.",
          },
          {
            id: "c-5",
            document_name: "IT-Equipment-List-2026.pdf",
            source_location: "page 2",
            excerpt:
              "Standard contractor issue: MacBook Air 13\" (M3, 16 GB / 512 GB). Returned within five working days of the contract end date to the Rotterdam office or via the prepaid courier label issued by IT.",
          },
          {
            id: "c-6",
            document_name: "Contractor-Onboarding-2024.pdf",
            source_location: "page 7",
            missing: true,
            excerpt: "",
          },
        ],
      },
    ],
  },
  {
    id: "t-3",
    title: "Refunds on annual plans after 30 days",
    created_at: "2026-10-14T14:12:00",
    last_active_at: "2026-10-14T14:21:00",
    messages: [
      {
        id: "m-7",
        role: "user",
        author: "A visitor",
        status: "complete",
        created_at: "2026-10-14T14:12:00",
        content: "Do we refund annual plans after the first 30 days?",
      },
      {
        id: "m-8",
        role: "assistant",
        status: "complete",
        created_at: "2026-10-14T14:13:00",
        content:
          "No. Annual plans are refundable in full within the first 30 days of the term. After day 30 the policy is no refund for the remainder of the term; the plan stays active until its end date and simply does not renew.\n\nThe one exception listed is a documented service failure of more than 72 consecutive hours, which is credited pro rata rather than refunded.",
        citations: [
          {
            id: "c-7",
            document_name: "Refund-Policy-2026-Q3.pdf",
            source_location: "page 3",
            excerpt:
              "3.1 Annual subscriptions may be cancelled with a full refund within thirty (30) calendar days of the start of the term. 3.2 After day 30, no refund is issued for the unused portion. 3.3 A verified outage exceeding 72 consecutive hours is compensated as account credit, calculated pro rata against the annual fee.",
          },
        ],
      },
      {
        id: "m-9",
        role: "user",
        author: "A visitor",
        status: "complete",
        created_at: "2026-10-14T14:21:00",
        content: "What happens if a customer downgrades mid-term instead of cancelling?",
      },
      {
        id: "m-10",
        role: "assistant",
        status: "error",
        created_at: "2026-10-14T14:21:00",
        content: "",
        failure_reason: "Gemini stopped responding after 30 seconds (504 from generateContent).",
        citations: [],
      },
    ],
  },
  {
    id: "t-4",
    title: "Berlin office Christmas closure",
    created_at: "2026-10-13T09:02:00",
    last_active_at: "2026-10-13T09:05:00",
    messages: [
      {
        id: "m-11",
        role: "user",
        author: "A visitor",
        status: "complete",
        created_at: "2026-10-13T09:02:00",
        content: "When is the Berlin office closed over Christmas?",
      },
      {
        id: "m-12",
        role: "assistant",
        status: "incomplete",
        created_at: "2026-10-13T09:05:00",
        content:
          "The Berlin office closes from Thursday 24 December 2026 and reopens on Monday 4 January 2027. Over that period the handbook asks each team to leave one named contact reachable for",
        citations: [],
      },
    ],
  },
  {
    id: "t-5",
    title: "What's the capital of Peru?",
    created_at: "2026-10-09T15:48:00",
    last_active_at: "2026-10-09T15:48:00",
    messages: [
      {
        id: "m-13",
        role: "user",
        author: "A visitor",
        status: "complete",
        created_at: "2026-10-09T15:48:00",
        content: "What's the capital of Peru?",
      },
      {
        id: "m-14",
        role: "assistant",
        status: "complete",
        created_at: "2026-10-09T15:48:00",
        content:
          "I can't answer that from the uploaded documents. Nothing in the library covers it, and I don't answer from general knowledge.\n\nThe library currently holds HR, security, finance and office files. Ask about one of those, or add a document on the documents screen.",
        citations: [],
      },
    ],
  },
  {
    id: "t-6",
    title: "Per-head limit for client dinners",
    created_at: "2026-10-06T10:17:00",
    last_active_at: "2026-10-06T10:19:00",
    messages: [
      {
        id: "m-15",
        role: "user",
        author: "A visitor",
        status: "complete",
        created_at: "2026-10-06T10:17:00",
        content: "What's the per-head limit for client dinners, and does it include drinks?",
      },
      {
        id: "m-16",
        role: "assistant",
        status: "complete",
        created_at: "2026-10-06T10:19:00",
        content:
          "€65 per head in Europe and $75 per head in the United States, and yes — the cap includes drinks and service. Anything above the cap needs written approval from a budget owner before the dinner, attached to the claim.",
        citations: [
          {
            id: "c-8",
            document_name: "Expenses-Policy-v4.docx",
            source_location: 'section 3.2 "Hospitality"',
            excerpt:
              "Client hospitality is capped at €65 per attendee (EU) and $75 per attendee (US), inclusive of beverages, service and local taxes. Claims above the cap require prior written approval from a budget owner, uploaded with the receipt. Alcohol is reimbursable within the cap but never as a standalone claim.",
          },
        ],
      },
    ],
  },
];

const INCOMING_THREAD = {
  id: "t-7",
  title: "Where do we file the Q3 VAT return?",
  created_at: "2026-10-16T12:06:00",
  last_active_at: "2026-10-16T12:08:00",
  isNew: true,
  messages: [
    {
      id: "m-17",
      role: "user",
      author: "A visitor",
      status: "complete",
      created_at: "2026-10-16T12:06:00",
      content: "Where do we file the Q3 VAT return and by which date?",
    },
    {
      id: "m-18",
      role: "assistant",
      status: "complete",
      created_at: "2026-10-16T12:08:00",
      content:
        "The Q3 return is filed through the Belastingdienst business portal by 31 October 2026. Finance prepares the figures from the Xero export on the last working day of the quarter and the filing itself is done by the external bookkeeper, who needs the export at least five working days ahead.",
      citations: [
        {
          id: "c-9",
          document_name: "Finance-Calendar-2026.pdf",
          source_location: "page 6",
          excerpt:
            "Q3 (Jul–Sep) VAT return: due 31 October. Owner: external bookkeeper (Van Dijk & Partners). Inputs required five working days before the deadline: Xero trial balance export, intra-community sales listing, receipts folder for the quarter.",
        },
      ],
    },
  ],
};

const ANSWER_BOOK = [
  {
    test: /dinner|expense|meal|hospitality|entertain|claim|receipt/i,
    text:
      "Client dinners are capped at €65 per head in Europe and $75 per head in the United States, including drinks, service and local taxes.\n\nAnything above the cap needs written approval from a budget owner before the dinner, uploaded with the receipt. Alcohol is reimbursable inside the cap but never as a claim on its own.",
    citations: [
      {
        document_name: "Expenses-Policy-v4.docx",
        source_location: 'section 3.2 "Hospitality"',
        excerpt:
          "Client hospitality is capped at €65 per attendee (EU) and $75 per attendee (US), inclusive of beverages, service and local taxes. Claims above the cap require prior written approval from a budget owner, uploaded with the receipt.",
      },
      {
        document_name: "People-Handbook-2026.pdf",
        source_location: "page 51",
        excerpt:
          "Expenses are reimbursed in the payroll run following approval. Claims older than 60 days are not reimbursed without a written exception from Finance.",
      },
    ],
  },
  {
    test: /laptop|device|hardware|macbook|windows|byod|encrypt/i,
    text:
      "Contractors can take a company-issued MacBook Air (M3, 16 GB) or bring their own machine if it meets the baseline: full-disk encryption on, OS within one major version of current, five-minute screen lock, and MDM enrolled before shared-drive access.\n\nWindows is fine under the same baseline. Linux can't be enrolled in the MDM agent, so it isn't supported.",
    citations: [
      {
        document_name: "Security-Baseline.md",
        source_location: 'section 4.2 "Contractor devices"',
        excerpt:
          "Bring-your-own devices are permitted provided all four baseline controls are verifiable at enrolment: FileVault or BitLocker enabled, OS no more than one major version behind, automatic lock at five minutes, and successful MDM check-in.",
      },
      {
        document_name: "IT-Equipment-List-2026.pdf",
        source_location: "page 2",
        excerpt:
          "Standard contractor issue: MacBook Air 13\" (M3, 16 GB / 512 GB), returned within five working days of the contract end date.",
      },
    ],
  },
  {
    test: /leave|parental|maternity|paternity|elterngeld|holiday allowance|sick/i,
    text:
      "Dutch staff get the statutory parental benefit (70% of salary for 9 of the 26 weeks, paid by UWV) topped up by the company to 100% of base salary for those nine weeks. The remaining seventeen weeks are unpaid.\n\nPeople Ops needs four weeks' notice before the first day of leave for the top-up to make that month's payroll run.",
    citations: [
      {
        document_name: "People-Handbook-2026.pdf",
        source_location: "page 34",
        excerpt:
          "For nine of those weeks UWV pays 70% of daily wages; Section 6 commits the company to topping this payment up to 100% of base salary. The remaining seventeen weeks are unpaid.",
      },
      {
        document_name: "Benefits-NL-2026.docx",
        source_location: 'section 4.1 "Leave top-ups"',
        excerpt:
          "Top-ups are processed through the regular monthly payroll run and appear as a separate line item (code PLT-100). People Ops requires four weeks' notice ahead of the first day of leave.",
      },
    ],
  },
  {
    test: /refund|cancel|annual plan|billing|downgrade|subscription/i,
    text:
      "Annual plans are refundable in full inside the first 30 days of the term. After day 30 there's no refund for the unused portion — the plan runs to its end date and then doesn't renew.\n\nThe only exception is a verified outage of more than 72 consecutive hours, which is compensated as pro-rata account credit rather than cash.",
    citations: [
      {
        document_name: "Refund-Policy-2026-Q3.pdf",
        source_location: "page 3",
        excerpt:
          "3.1 Annual subscriptions may be cancelled with a full refund within thirty (30) calendar days of the start of the term. 3.2 After day 30, no refund is issued for the unused portion. 3.3 A verified outage exceeding 72 consecutive hours is compensated as account credit, calculated pro rata.",
      },
    ],
  },
  {
    test: /office|closure|christmas|opening hours|berlin|reopen|desk/i,
    text:
      "The Berlin office closes from Thursday 24 December 2026 and reopens Monday 4 January 2027. Rotterdam closes on 25 and 26 December and 1 January only.\n\nDuring the Berlin closure each team leaves one named contact reachable for customer escalations; the rota is agreed in the first week of December.",
    citations: [
      {
        document_name: "Office-Closures-2026.txt",
        source_location: "lines 12–20",
        excerpt:
          "BERLIN — closed 24 Dec 2026 through 1 Jan 2027 inclusive, reopening Mon 4 Jan. ROTTERDAM — closed 25 Dec, 26 Dec, 1 Jan. Escalation rota to be agreed by 5 December and posted in #ops.",
      },
      {
        document_name: "People-Handbook-2026.pdf",
        source_location: "page 22",
        excerpt:
          "Office closure days are not deducted from the annual holiday allowance. Staff rostered for escalation cover during a closure take the equivalent time back in January.",
      },
    ],
  },
];

const NOT_FOUND_TEXT =
  "I couldn't find that in the uploaded documents, so I'm not going to guess at it.\n\nThe library currently covers HR and benefits, security and device policy, refunds and finance, and office closures. Try rephrasing towards one of those, or upload the file that would answer it on the documents screen.";

export default function Screen() {
  const navigate = useNavigate();
  const { Button, Input, Textarea } = UI;
  const {
    Plus,
    Search,
    Trash,
    Edit,
    X,
    ChevronRight,
    ChevronDown,
    AlertCircle,
    CheckCircle,
    FileText,
    Clock,
    ArrowRight,
    Users,
  } = Icons;

  const primary = brand.primaryColor;
  const accent = brand.accentColor;
  const neutral = brand.neutralColor;
  const ink = "#1C1917";
  const line = neutral + "33";
  const softLine = neutral + "22";
  const surface = "#FFFFFF";
  const r = brand.radius;

  const reduceMotion = React.useMemo(
    () =>
      typeof window !== "undefined" &&
      window.matchMedia &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches,
    []
  );

  const [threads, setThreads] = React.useState(SEED_THREADS);
  const [activeId, setActiveId] = React.useState("t-1");
  const [query, setQuery] = React.useState("");
  const [draft, setDraft] = React.useState("");
  const [expanded, setExpanded] = React.useState({});
  const [stream, setStream] = React.useState(null);
  const [loadingThread, setLoadingThread] = React.useState(false);
  const [dialog, setDialog] = React.useState(null);
  const [renameValue, setRenameValue] = React.useState("");
  const [renameError, setRenameError] = React.useState("");
  const [sync, setSync] = React.useState({ state: "idle", label: "11:42" });
  const [threadsOpenMobile, setThreadsOpenMobile] = React.useState(false);

  const composerRef = React.useRef(null);
  const scrollRef = React.useRef(null);
  const dialogRef = React.useRef(null);
  const triggerRef = React.useRef(null);

  const active = threads.find((t) => t.id === activeId) || null;

  const fmt = (iso) => {
    const d = new Date(iso);
    const now = new Date();
    const hh = String(d.getHours()).padStart(2, "0");
    const mm = String(d.getMinutes()).padStart(2, "0");
    const sameDay = d.toDateString() === now.toDateString();
    const y = new Date(now.getTime() - 86400000);
    if (sameDay) return hh + ":" + mm;
    if (d.toDateString() === y.toDateString()) return "Yesterday " + hh + ":" + mm;
    return d.getDate() + " " + MONTHS[d.getMonth()];
  };

  const filtered = threads
    .slice()
    .sort((a, b) => new Date(b.last_active_at) - new Date(a.last_active_at))
    .filter((t) => t.title.toLowerCase().includes(query.trim().toLowerCase()));

  // ---- streaming ----
  React.useEffect(() => {
    if (!stream) return undefined;
    if (stream.shown >= stream.text.length) {
      const finishedAt = new Date().toISOString();
      const mid = "m-" + Math.random().toString(36).slice(2, 8);
      setThreads((prev) =>
        prev.map((t) =>
          t.id === stream.threadId
            ? {
                ...t,
                last_active_at: finishedAt,
                messages: [
                  ...t.messages,
                  {
                    id: mid,
                    role: "assistant",
                    status: "complete",
                    created_at: finishedAt,
                    content: stream.text,
                    citations: stream.citations.map((c, i) => ({ ...c, id: mid + "-c" + i })),
                  },
                ],
              }
            : t
        )
      );
      setStream(null);
      return undefined;
    }
    const step = reduceMotion ? stream.text.length : 3 + Math.floor(Math.random() * 5);
    const timer = setTimeout(
      () => setStream((s) => (s ? { ...s, shown: Math.min(s.text.length, s.shown + step) } : s)),
      reduceMotion ? 120 : 18
    );
    return () => clearTimeout(timer);
  }, [stream, reduceMotion]);

  React.useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [activeId, stream, threads, loadingThread]);

  React.useEffect(() => {
    if (!dialog) return undefined;
    const t = setTimeout(() => {
      if (!dialogRef.current) return;
      const first = dialogRef.current.querySelector(dialog.mode === "rename" ? "input" : "button[data-confirm]");
      if (first) first.focus();
    }, 20);
    return () => clearTimeout(t);
  }, [dialog]);

  const openThread = (id) => {
    if (id === activeId) {
      setThreadsOpenMobile(false);
      return;
    }
    setActiveId(id);
    setThreadsOpenMobile(false);
    setLoadingThread(true);
    setTimeout(() => setLoadingThread(false), reduceMotion ? 0 : 320);
  };

  const buildAnswer = (question) => {
    const hit = ANSWER_BOOK.find((a) => a.test.test(question));
    if (!hit) return { text: NOT_FOUND_TEXT, citations: [] };
    return { text: hit.text, citations: hit.citations };
  };

  const send = (text) => {
    const q = text.trim();
    if (!q || stream) return;
    const nowIso = new Date().toISOString();
    const userMsg = {
      id: "m-" + Math.random().toString(36).slice(2, 8),
      role: "user",
      author: "You",
      status: "complete",
      created_at: nowIso,
      content: q,
    };
    let targetId = activeId;
    if (!active) {
      targetId = "t-" + Math.random().toString(36).slice(2, 8);
      const title = q.replace(/\s+/g, " ").trim();
      setThreads((prev) => [
        {
          id: targetId,
          title: title.length > 52 ? title.slice(0, 52).trimEnd() + "…" : title,
          created_at: nowIso,
          last_active_at: nowIso,
          messages: [userMsg],
        },
        ...prev,
      ]);
      setActiveId(targetId);
    } else {
      setThreads((prev) =>
        prev.map((t) =>
          t.id === targetId ? { ...t, last_active_at: nowIso, messages: [...t.messages, userMsg] } : t
        )
      );
    }
    const ans = buildAnswer(q);
    setDraft("");
    setStream({ threadId: targetId, text: ans.text, citations: ans.citations, shown: 0 });
  };

  const retry = (threadId, errorMessageId) => {
    const t = threads.find((x) => x.id === threadId);
    if (!t) return;
    const idx = t.messages.findIndex((m) => m.id === errorMessageId);
    const question = idx > 0 ? t.messages[idx - 1].content : "";
    setThreads((prev) =>
      prev.map((x) => (x.id === threadId ? { ...x, messages: x.messages.filter((m) => m.id !== errorMessageId) } : x))
    );
    const ans = buildAnswer(question);
    setStream({ threadId, text: ans.text, citations: ans.citations, shown: 0 });
  };

  const closeDialog = () => {
    setDialog(null);
    setRenameError("");
    if (triggerRef.current && triggerRef.current.focus) triggerRef.current.focus();
  };

  const onDialogKeyDown = (e) => {
    if (e.key === "Escape") {
      e.stopPropagation();
      closeDialog();
      return;
    }
    if (e.key === "Tab" && dialogRef.current) {
      const nodes = Array.prototype.slice
        .call(dialogRef.current.querySelectorAll("button, input, textarea, a[href]"))
        .filter((n) => !n.disabled);
      if (!nodes.length) return;
      const first = nodes[0];
      const last = nodes[nodes.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }
  };

  const saveRename = () => {
    const v = renameValue.trim();
    if (!v) {
      setRenameError("A conversation needs a name. The old one has been kept.");
      return;
    }
    setThreads((prev) => prev.map((t) => (t.id === dialog.threadId ? { ...t, title: v } : t)));
    closeDialog();
  };

  const confirmDelete = () => {
    const id = dialog.threadId;
    setThreads((prev) => prev.filter((t) => t.id !== id));
    if (id === activeId) setActiveId(null);
    closeDialog();
  };

  const checkUpdates = () => {
    if (sync.state === "checking") return;
    setSync({ state: "checking", label: sync.label });
    setTimeout(() => {
      if (threads.some((t) => t.id === INCOMING_THREAD.id)) {
        setSync({ state: "current", label: "just now" });
      } else {
        setThreads((prev) => [INCOMING_THREAD, ...prev]);
        setSync({ state: "new", label: "just now" });
      }
    }, 650);
  };

  const toggleCitation = (key) => setExpanded((p) => ({ ...p, [key]: !p[key] }));

  const smallLabel = "text-[11px] uppercase tracking-[0.09em] font-semibold";
  const focusRing = "focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2";

  const statusChip = (label, icon, color) => (
    <span
      className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium"
      style={{ backgroundColor: color + "14", color: color, fontVariantNumeric: "tabular-nums" }}
    >
      {icon}
      {label}
    </span>
  );

  const renderCitations = (msg) => {
    if (!msg.citations || !msg.citations.length) return null;
    return (
      <div className="mt-5">
        <h4 className={smallLabel} style={{ color: neutral }}>
          Sources · {msg.citations.length}
        </h4>
        <ul className="mt-2 space-y-2">
          {msg.citations.map((c) => {
            const key = msg.id + ":" + c.id;
            const open = !!expanded[key];
            return (
              <li key={c.id}>
                <button
                  type="button"
                  onClick={() => toggleCitation(key)}
                  aria-expanded={open}
                  className={
                    "w-full flex items-start gap-2.5 text-left px-3 py-2.5 transition-colors " + focusRing
                  }
                  style={{
                    border: "1px solid " + (open ? accent + "66" : line),
                    borderRadius: r,
                    backgroundColor: open ? accent + "0D" : surface,
                    color: ink,
                  }}
                >
                  <span className="mt-0.5 shrink-0" style={{ color: accent }} aria-hidden="true">
                    {open ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                  </span>
                  <span className="flex-1 text-sm leading-snug">
                    <span className="font-semibold" style={{ color: accent }}>
                      {c.document_name}
                    </span>
                    <span style={{ color: neutral }}> — {c.source_location}</span>
                    {c.missing ? (
                      <span className="ml-2 font-medium" style={{ color: primary }}>
                        · deleted
                      </span>
                    ) : null}
                  </span>
                  <span className={smallLabel + " shrink-0 mt-0.5"} style={{ color: neutral }}>
                    {open ? "Hide" : "Read"}
                  </span>
                </button>
                {open ? (
                  <div className="anim-in mt-2 ml-7">
                    {c.missing ? (
                      <p
                        className="text-sm leading-relaxed px-3 py-3"
                        style={{
                          color: neutral,
                          borderLeft: "3px solid " + primary,
                          backgroundColor: primary + "0A",
                          borderRadius: "0 " + r + " " + r + " 0",
                        }}
                      >
                        <strong style={{ color: ink }}>{c.document_name}</strong> is no longer in the library —
                        someone deleted it after this answer was written, so the excerpt can't be shown. The answer
                        above is kept as it was.
                      </p>
                    ) : (
                      <blockquote
                        className="text-sm leading-relaxed px-3 py-3"
                        style={{
                          color: ink,
                          borderLeft: "3px solid " + accent,
                          backgroundColor: accent + "0A",
                          borderRadius: "0 " + r + " " + r + " 0",
                        }}
                      >
                        {c.excerpt}
                        <footer className={smallLabel + " mt-2 not-italic"} style={{ color: neutral }}>
                          Retrieved chunk · {c.document_name} · {c.source_location}
                        </footer>
                      </blockquote>
                    )}
                  </div>
                ) : null}
              </li>
            );
          })}
        </ul>
      </div>
    );
  };

  const renderMessage = (m) => {
    if (m.role === "user") {
      return (
        <li key={m.id} className="anim-in flex justify-end">
          <div
            className="max-w-[88%] sm:max-w-[80%] px-4 py-3"
            style={{ backgroundColor: primary + "0F", border: "1px solid " + primary + "2E", borderRadius: r }}
          >
            <p className={smallLabel} style={{ color: primary, fontVariantNumeric: "tabular-nums" }}>
              {m.author || "A visitor"} · {fmt(m.created_at)}
            </p>
            <p className="mt-1.5 text-[15px] leading-relaxed" style={{ color: ink }}>
              {m.content}
            </p>
          </div>
        </li>
      );
    }

    if (m.status === "error") {
      return (
        <li key={m.id} className="anim-in">
          <div
            className="px-4 py-4"
            style={{ border: "1px solid " + primary + "40", borderRadius: r, backgroundColor: primary + "08" }}
          >
            <p className="flex items-center gap-2 font-semibold text-[15px]" style={{ color: primary }}>
              <AlertCircle className="w-4 h-4" aria-hidden="true" />
              Gemini didn't finish this answer
            </p>
            <p className="mt-2 text-sm leading-relaxed" style={{ color: ink }}>
              {m.failure_reason} Nothing was written to the thread, so the conversation is intact.
            </p>
            <p className="mt-2 text-sm" style={{ color: neutral }}>
              Your question is still here and can be sent again as it was.
            </p>
            <div className="mt-3">
              <Button
                type="button"
                onClick={() => retry(active.id, m.id)}
                className={"inline-flex items-center gap-2 px-4 py-2 text-sm font-semibold " + focusRing}
                style={{ backgroundColor: primary, color: "#FFFFFF", borderRadius: r }}
              >
                <ArrowRight className="w-4 h-4" aria-hidden="true" />
                Ask it again
              </Button>
            </div>
          </div>
        </li>
      );
    }

    return (
      <li key={m.id} className="anim-in">
        <div className="flex items-center gap-2">
          <span
            className="inline-flex items-center justify-center w-6 h-6 rounded-full"
            style={{ backgroundColor: accent + "1A", color: accent }}
            aria-hidden="true"
          >
            <FileText className="w-3.5 h-3.5" />
          </span>
          <p className={smallLabel} style={{ color: neutral, fontVariantNumeric: "tabular-nums" }}>
            From the library · {fmt(m.created_at)}
          </p>
        </div>
        <div className="mt-2 pl-8">
          {m.content.split("\n\n").map((p, i) => (
            <p key={i} className={(i ? "mt-3 " : "") + "text-[15px] leading-[1.7]"} style={{ color: ink }}>
              {p}
            </p>
          ))}
          {m.status === "incomplete" ? (
            <div
              className="mt-4 px-3 py-3 text-sm"
              style={{ border: "1px dashed " + neutral + "66", borderRadius: r, color: neutral }}
            >
              <strong style={{ color: ink }}>Answer stopped early.</strong> The connection dropped while Gemini was
              streaming, so this one was stored unfinished. Ask it again to get a complete answer.
              <div className="mt-3">
                <Button
                  type="button"
                  onClick={() => retry(active.id, m.id)}
                  className={"inline-flex items-center gap-2 px-3.5 py-1.5 text-sm font-semibold " + focusRing}
                  style={{ backgroundColor: surface, color: primary, border: "1px solid " + primary + "66", borderRadius: r }}
                >
                  Ask it again
                </Button>
              </div>
            </div>
          ) : null}
          {!m.citations || !m.citations.length ? (
            m.status === "complete" ? (
              <p className={smallLabel + " mt-4"} style={{ color: neutral }}>
                No sources — nothing in the library matched closely enough to cite
              </p>
            ) : null
          ) : (
            renderCitations(m)
          )}
        </div>
      </li>
    );
  };

  return (
    <div
      className="w-full"
      style={{ backgroundColor: brand.backgroundColor, fontFamily: brand.fontBody, color: ink }}
    >
      <style>{`
        @keyframes nb-in { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: none; } }
        @keyframes nb-pop { from { opacity: 0; transform: scale(.97) translateY(8px); } to { opacity: 1; transform: none; } }
        @keyframes nb-blink { 0%,45% { opacity: 1 } 50%,100% { opacity: 0 } }
        @keyframes nb-pulse { 0%,100% { opacity: .35 } 50% { opacity: 1 } }
        .anim-in { animation: nb-in .28s ease-out both; }
        .anim-pop { animation: nb-pop .18s ease-out both; }
        .caret { display:inline-block; width:2px; height:1.05em; vertical-align:-0.15em; margin-left:2px; animation: nb-blink 1s steps(1) infinite; }
        .pulse-dot { animation: nb-pulse 1.1s ease-in-out infinite; }
        @media (prefers-reduced-motion: reduce) {
          .anim-in, .anim-pop, .caret, .pulse-dot { animation: none !important; }
        }
      `}</style>

      <div className="mx-auto max-w-[1180px] px-4 sm:px-6 py-7">
        <header>
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <h1
                className="text-3xl sm:text-[34px] font-bold tracking-tight"
                style={{ fontFamily: brand.fontHeading, color: ink }}
              >
                Ask the shared library
              </h1>
              <p className="mt-2 text-[15px] max-w-2xl leading-relaxed" style={{ color: neutral }}>
                Every question searches all {LIBRARY.ready} indexed documents — there's nothing to pick from. Answers
                come only from those files, with the page or section they came from.
              </p>
            </div>
            <Button
              type="button"
              onClick={() => navigate("documents")}
              className={"inline-flex items-center gap-2 px-4 py-2.5 text-sm font-semibold " + focusRing}
              style={{ backgroundColor: surface, color: ink, border: "1px solid " + line, borderRadius: r }}
            >
              <FileText className="w-4 h-4" aria-hidden="true" />
              Manage documents
            </Button>
          </div>

          <div
            className="mt-5 flex flex-wrap items-center gap-x-3 gap-y-2 px-4 py-3"
            style={{ backgroundColor: surface, border: "1px solid " + softLine, borderRadius: r }}
          >
            {statusChip(LIBRARY.ready + " ready", <CheckCircle className="w-3.5 h-3.5" aria-hidden="true" />, accent)}
            {statusChip(
              LIBRARY.processing + " indexing",
              <Clock className="w-3.5 h-3.5 pulse-dot" aria-hidden="true" />,
              neutral
            )}
            {statusChip(LIBRARY.failed + " failed", <AlertCircle className="w-3.5 h-3.5" aria-hidden="true" />, primary)}
            <span className="hidden sm:inline-block w-px h-5" style={{ backgroundColor: line }} aria-hidden="true" />
            <p className="text-sm flex items-center gap-1.5" style={{ color: neutral }}>
              <Users className="w-4 h-4" aria-hidden="true" />
              Open to anyone with the link. No accounts — everyone sees these threads.
            </p>
            <Button
              type="button"
              onClick={() => navigate("setup")}
              className={"ml-auto text-sm font-semibold underline underline-offset-4 px-1 " + focusRing}
              style={{ backgroundColor: "transparent", color: accent, borderRadius: r }}
            >
              Setup &amp; status
            </Button>
          </div>
        </header>

        <div className="mt-6 grid grid-cols-1 lg:grid-cols-12 gap-5">
          {/* ---------------- Sidebar ---------------- */}
          <div className="lg:col-span-4 xl:col-span-3 order-2 lg:order-1">
            <Button
              type="button"
              onClick={() => setThreadsOpenMobile((v) => !v)}
              aria-expanded={threadsOpenMobile}
              className={"lg:hidden w-full flex items-center justify-between px-4 py-3 text-sm font-semibold mb-3 " + focusRing}
              style={{ backgroundColor: surface, color: ink, border: "1px solid " + line, borderRadius: r }}
            >
              <span style={{ fontVariantNumeric: "tabular-nums" }}>Conversations ({threads.length})</span>
              {threadsOpenMobile ? (
                <ChevronDown className="w-4 h-4" aria-hidden="true" />
              ) : (
                <ChevronRight className="w-4 h-4" aria-hidden="true" />
              )}
            </Button>

            <aside
              className={(threadsOpenMobile ? "block " : "hidden ") + "lg:block"}
              aria-label="Shared conversations"
            >
              <div
                className="p-4"
                style={{ backgroundColor: surface, border: "1px solid " + softLine, borderRadius: r }}
              >
                <div className="flex items-baseline justify-between gap-2">
                  <h2 className="text-base font-bold tracking-tight" style={{ fontFamily: brand.fontHeading }}>
                    Conversations
                  </h2>
                  <span className={smallLabel} style={{ color: neutral, fontVariantNumeric: "tabular-nums" }}>
                    {threads.length} shared
                  </span>
                </div>

                <Button
                  type="button"
                  onClick={() => {
                    setActiveId(null);
                    setDraft("");
                    setThreadsOpenMobile(false);
                    if (composerRef.current) composerRef.current.focus();
                  }}
                  className={"mt-3 w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-semibold " + focusRing}
                  style={{ backgroundColor: primary + "0F", color: primary, border: "1px solid " + primary + "4D", borderRadius: r }}
                >
                  <Plus className="w-4 h-4" aria-hidden="true" />
                  New conversation
                </Button>

                <div className="mt-4">
                  <label htmlFor="thread-search" className={smallLabel + " block mb-1.5"} style={{ color: neutral }}>
                    Find a thread
                  </label>
                  <div className="relative">
                    <span
                      className="absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none"
                      style={{ color: neutral }}
                      aria-hidden="true"
                    >
                      <Search className="w-4 h-4" />
                    </span>
                    <Input
                      id="thread-search"
                      type="text"
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                      placeholder="refunds, laptops, leave…"
                      className={"w-full pl-9 pr-3 py-2 text-sm " + focusRing}
                      style={{
                        backgroundColor: brand.backgroundColor,
                        border: "1px solid " + line,
                        borderRadius: r,
                        color: ink,
                      }}
                    />
                  </div>
                </div>

                <div className="mt-4 max-h-[52vh] overflow-y-auto -mx-1 px-1">
                  {threads.length === 0 ? (
                    <div className="py-8 text-center">
                      <p className="text-sm font-semibold" style={{ color: ink }}>
                        Nothing on the board yet
                      </p>
                      <p className="mt-1.5 text-sm leading-relaxed" style={{ color: neutral }}>
                        Ask the first question and it'll appear here for everyone with the link.
                      </p>
                    </div>
                  ) : filtered.length === 0 ? (
                    <div className="py-8 text-center">
                      <p className="text-sm font-semibold" style={{ color: ink }}>
                        No thread matches “{query.trim()}”
                      </p>
                      <p className="mt-1.5 text-sm" style={{ color: neutral }}>
                        Search looks at titles only.
                      </p>
                      <Button
                        type="button"
                        onClick={() => setQuery("")}
                        className={"mt-3 px-3 py-1.5 text-sm font-semibold " + focusRing}
                        style={{ backgroundColor: "transparent", color: accent, borderRadius: r }}
                      >
                        Clear search
                      </Button>
                    </div>
                  ) : (
                    <ul className="space-y-1.5">
                      {filtered.map((t) => {
                        const isActive = t.id === activeId;
                        return (
                          <li
                            key={t.id}
                            className={t.isNew ? "anim-in" : ""}
                            style={{
                              borderRadius: r,
                              backgroundColor: isActive ? primary + "0F" : "transparent",
                              borderLeft: "3px solid " + (isActive ? primary : "transparent"),
                            }}
                          >
                            <div className="flex items-stretch">
                              <button
                                type="button"
                                onClick={() => openThread(t.id)}
                                aria-current={isActive ? "true" : undefined}
                                className={"flex-1 text-left px-3 py-2.5 min-w-0 " + focusRing}
                                style={{ borderRadius: r }}
                              >
                                <span
                                  className="block text-sm font-semibold leading-snug truncate"
                                  style={{ color: isActive ? primary : ink }}
                                >
                                  {t.title}
                                </span>
                                <span
                                  className="block mt-0.5 text-xs"
                                  style={{ color: neutral, fontVariantNumeric: "tabular-nums" }}
                                >
                                  {t.messages.length} messages · {fmt(t.last_active_at)}
                                </span>
                              </button>
                              <div className="flex items-center gap-0.5 pr-1">
                                <button
                                  type="button"
                                  aria-label={"Rename “" + t.title + "”"}
                                  onClick={(e) => {
                                    triggerRef.current = e.currentTarget;
                                    setRenameValue(t.title);
                                    setRenameError("");
                                    setDialog({ mode: "rename", threadId: t.id, title: t.title });
                                  }}
                                  className={"p-2 rounded " + focusRing}
                                  style={{ color: neutral }}
                                >
                                  <Edit className="w-4 h-4" aria-hidden="true" />
                                </button>
                                <button
                                  type="button"
                                  aria-label={"Delete “" + t.title + "”"}
                                  onClick={(e) => {
                                    triggerRef.current = e.currentTarget;
                                    setDialog({ mode: "delete", threadId: t.id, title: t.title });
                                  }}
                                  className={"p-2 rounded " + focusRing}
                                  style={{ color: neutral }}
                                >
                                  <Trash className="w-4 h-4" aria-hidden="true" />
                                </button>
                              </div>
                            </div>
                          </li>
                        );
                      })}
                    </ul>
                  )}
                </div>

                <div className="mt-4 pt-3" style={{ borderTop: "1px solid " + softLine }}>
                  <p className="text-xs leading-relaxed" style={{ color: neutral, fontVariantNumeric: "tabular-nums" }}>
                    {sync.state === "new"
                      ? "1 new thread arrived from another visitor."
                      : sync.state === "current"
                      ? "You're up to date with everyone else."
                      : "Shared list · last synced " + sync.label}
                  </p>
                  <Button
                    type="button"
                    onClick={checkUpdates}
                    className={"mt-2 inline-flex items-center gap-2 text-xs font-semibold px-2.5 py-1.5 " + focusRing}
                    style={{ backgroundColor: "transparent", color: accent, border: "1px solid " + line, borderRadius: r }}
                  >
                    {sync.state === "checking" ? (
                      <React.Fragment>
                        <Clock className="w-3.5 h-3.5 pulse-dot" aria-hidden="true" />
                        Checking…
                      </React.Fragment>
                    ) : (
                      <React.Fragment>
                        <Users className="w-3.5 h-3.5" aria-hidden="true" />
                        Check for new activity
                      </React.Fragment>
                    )}
                  </Button>
                </div>
              </div>
            </aside>
          </div>

          {/* ---------------- Conversation ---------------- */}
          <main className="lg:col-span-8 xl:col-span-9 order-1 lg:order-2">
            <section
              className="flex flex-col"
              style={{ backgroundColor: surface, border: "1px solid " + softLine, borderRadius: r }}
              aria-label="Conversation"
            >
              <div
                className="flex flex-wrap items-start justify-between gap-3 px-5 sm:px-6 py-4"
                style={{ borderBottom: "1px solid " + softLine }}
              >
                <div className="min-w-0">
                  <h2
                    className="text-lg font-bold tracking-tight truncate"
                    style={{ fontFamily: brand.fontHeading, color: ink }}
                  >
                    {active ? active.title : "New conversation"}
                  </h2>
                  <p className="mt-1 text-xs" style={{ color: neutral, fontVariantNumeric: "tabular-nums" }}>
                    {active
                      ? active.messages.length +
                        " messages · started " +
                        fmt(active.created_at) +
                        " · last active " +
                        fmt(active.last_active_at)
                      : "Not saved yet — it joins the shared list when you send the first question"}
                  </p>
                </div>
                {active ? (
                  <div className="flex items-center gap-2">
                    <Button
                      type="button"
                      onClick={(e) => {
                        triggerRef.current = e.currentTarget;
                        setRenameValue(active.title);
                        setRenameError("");
                        setDialog({ mode: "rename", threadId: active.id, title: active.title });
                      }}
                      className={"inline-flex items-center gap-2 px-3 py-1.5 text-sm font-semibold " + focusRing}
                      style={{ backgroundColor: "transparent", color: ink, border: "1px solid " + line, borderRadius: r }}
                    >
                      <Edit className="w-4 h-4" aria-hidden="true" />
                      Rename
                    </Button>
                    <Button
                      type="button"
                      onClick={(e) => {
                        triggerRef.current = e.currentTarget;
                        setDialog({ mode: "delete", threadId: active.id, title: active.title });
                      }}
                      className={"inline-flex items-center gap-2 px-3 py-1.5 text-sm font-semibold " + focusRing}
                      style={{ backgroundColor: "transparent", color: primary, border: "1px solid " + primary + "40", borderRadius: r }}
                    >
                      <Trash className="w-4 h-4" aria-hidden="true" />
                      Delete
                    </Button>
                  </div>
                ) : null}
              </div>

              <div ref={scrollRef} className="px-5 sm:px-6 py-6 overflow-y-auto" style={{ maxHeight: "56vh", minHeight: "320px" }}>
                {loadingThread ? (
                  <div aria-live="polite">
                    <p className={smallLabel} style={{ color: neutral }}>
                      Loading the thread and its citations…
                    </p>
                    <div className="mt-4 space-y-3">
                      {[88, 72, 94, 60].map((w, i) => (
                        <div
                          key={i}
                          className="pulse-dot"
                          style={{ height: "14px", width: w + "%", backgroundColor: neutral + "26", borderRadius: r }}
                        />
                      ))}
                    </div>
                  </div>
                ) : !active ? (
                  <div className="py-6 max-w-2xl">
                    <h3 className="text-xl font-bold tracking-tight" style={{ fontFamily: brand.fontHeading }}>
                      Ask anything that's in the documents
                    </h3>
                    <p className="mt-2 text-[15px] leading-relaxed" style={{ color: neutral }}>
                      I read across all {LIBRARY.ready} indexed files and quote the page or section I used. If the
                      answer isn't in them, I'll say so rather than guess.
                    </p>
                    <ul className="mt-5 flex flex-wrap gap-2">
                      {STARTERS.map((s) => (
                        <li key={s}>
                          <button
                            type="button"
                            onClick={() => {
                              setDraft(s);
                              if (composerRef.current) composerRef.current.focus();
                            }}
                            className={"text-left text-sm px-3.5 py-2 transition-colors " + focusRing}
                            style={{ border: "1px solid " + line, borderRadius: r, color: ink, backgroundColor: brand.backgroundColor }}
                          >
                            {s}
                          </button>
                        </li>
                      ))}
                    </ul>
                    {LIBRARY.ready === 0 ? (
                      <p className="mt-6 text-sm" style={{ color: primary }}>
                        Nothing is indexed yet — upload a PDF, DOCX or Markdown file first.
                      </p>
                    ) : null}
                  </div>
                ) : (
                  <ul className="space-y-7">
                    {active.messages.map(renderMessage)}
                    {stream && stream.threadId === active.id ? (
                      <li className="anim-in" aria-live="polite">
                        <div className="flex items-center gap-2">
                          <span
                            className="inline-flex items-center justify-center w-6 h-6 rounded-full"
                            style={{ backgroundColor: accent + "1A", color: accent }}
                            aria-hidden="true"
                          >
                            <FileText className="w-3.5 h-3.5" />
                          </span>
                          <p className={smallLabel} style={{ color: accent }}>
                            Answering from the library…
                          </p>
                        </div>
                        <div className="mt-2 pl-8">
                          {stream.text
                            .slice(0, stream.shown)
                            .split("\n\n")
                            .map((p, i, arr) => (
                              <p
                                key={i}
                                className={(i ? "mt-3 " : "") + "text-[15px] leading-[1.7]"}
                                style={{ color: ink }}
                              >
                                {p}
                                {i === arr.length - 1 ? (
                                  <span className="caret" style={{ backgroundColor: primary }} aria-hidden="true" />
                                ) : null}
                              </p>
                            ))}
                          <p className={smallLabel + " mt-4"} style={{ color: neutral }}>
                            Sources appear when the answer finishes
                          </p>
                        </div>
                      </li>
                    ) : null}
                  </ul>
                )}
              </div>

              {/* Composer — the focal point */}
              <div className="px-5 sm:px-6 py-5" style={{ borderTop: "1px solid " + softLine, backgroundColor: brand.backgroundColor, borderRadius: "0 0 " + r + " " + r }}>
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    send(draft);
                  }}
                >
                  <label htmlFor="question" className={smallLabel + " block mb-2"} style={{ color: neutral }}>
                    Your question
                  </label>
                  <div className="flex flex-col sm:flex-row gap-3 items-stretch sm:items-end">
                    <Textarea
                      id="question"
                      ref={composerRef}
                      rows={2}
                      value={draft}
                      onChange={(e) => setDraft(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && !e.shiftKey) {
                          e.preventDefault();
                          send(draft);
                        }
                      }}
                      placeholder="What does the handbook say about notice periods?"
                      disabled={!!stream}
                      className={"flex-1 px-4 py-3 text-[15px] leading-relaxed resize-none " + focusRing}
                      style={{
                        backgroundColor: surface,
                        border: "1px solid " + line,
                        borderRadius: r,
                        color: ink,
                        opacity: stream ? 0.6 : 1,
                      }}
                    />
                    <Button
                      type="submit"
                      disabled={!!stream || !draft.trim()}
                      className={"inline-flex items-center justify-center gap-2 px-6 py-3.5 text-[15px] font-bold shrink-0 transition-opacity " + focusRing}
                      style={{
                        backgroundColor: primary,
                        color: "#FFFFFF",
                        borderRadius: r,
                        opacity: stream || !draft.trim() ? 0.55 : 1,
                        cursor: stream || !draft.trim() ? "not-allowed" : "pointer",
                      }}
                    >
                      {stream ? "Answering…" : "Ask the library"}
                      <ArrowRight className="w-4 h-4" aria-hidden="true" />
                    </Button>
                  </div>
                  <p className="mt-2.5 text-xs leading-relaxed" style={{ color: neutral }}>
                    Enter sends · Shift + Enter adds a line. Every question searches the whole library — follow-ups keep
                    this thread's earlier turns as context.
                  </p>
                </form>
              </div>
            </section>
          </main>
        </div>
      </div>

      {/* ---------------- Dialogs ---------------- */}
      {dialog ? (
        <div
          className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-4"
          style={{ backgroundColor: "rgba(28,25,23,0.45)" }}
          onMouseDown={(e) => {
            if (e.target === e.currentTarget) closeDialog();
          }}
        >
          <div
            ref={dialogRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby="dialog-title"
            onKeyDown={onDialogKeyDown}
            className="anim-pop w-full max-w-md p-6 shadow-2xl"
            style={{ backgroundColor: surface, borderRadius: r }}
          >
            <div className="flex items-start justify-between gap-4">
              <h2 id="dialog-title" className="text-lg font-bold tracking-tight" style={{ fontFamily: brand.fontHeading }}>
                {dialog.mode === "rename" ? "Rename this conversation" : "Delete this conversation?"}
              </h2>
              <button
                type="button"
                aria-label="Close dialog"
                onClick={closeDialog}
                className={"p-1.5 rounded " + focusRing}
                style={{ color: neutral }}
              >
                <X className="w-4 h-4" aria-hidden="true" />
              </button>
            </div>

            {dialog.mode === "rename" ? (
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  saveRename();
                }}
              >
                <p className="mt-2 text-sm leading-relaxed" style={{ color: neutral }}>
                  The new name is shown to everyone with the link.
                </p>
                <div className="mt-4">
                  <label htmlFor="thread-title" className={smallLabel + " block mb-1.5"} style={{ color: neutral }}>
                    Conversation name
                  </label>
                  <Input
                    id="thread-title"
                    type="text"
                    value={renameValue}
                    onChange={(e) => {
                      setRenameValue(e.target.value);
                      if (renameError) setRenameError("");
                    }}
                    aria-invalid={renameError ? "true" : undefined}
                    aria-describedby={renameError ? "rename-error" : undefined}
                    className={"w-full px-3 py-2.5 text-[15px] " + focusRing}
                    style={{
                      backgroundColor: brand.backgroundColor,
                      border: "1px solid " + (renameError ? primary : line),
                      borderRadius: r,
                      color: ink,
                    }}
                  />
                  {renameError ? (
                    <p id="rename-error" className="mt-2 text-sm flex items-start gap-1.5" style={{ color: primary }}>
                      <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" aria-hidden="true" />
                      {renameError}
                    </p>
                  ) : null}
                </div>
                <div className="mt-6 flex justify-end gap-2">
                  <Button
                    type="button"
                    onClick={closeDialog}
                    className={"px-4 py-2.5 text-sm font-semibold " + focusRing}
                    style={{ backgroundColor: "transparent", color: ink, border: "1px solid " + line, borderRadius: r }}
                  >
                    Cancel
                  </Button>
                  <Button
                    type="submit"
                    className={"px-4 py-2.5 text-sm font-bold " + focusRing}
                    style={{ backgroundColor: primary, color: "#FFFFFF", borderRadius: r }}
                  >
                    Save name
                  </Button>
                </div>
              </form>
            ) : (
              <div>
                <p className="mt-2 text-[15px] leading-relaxed" style={{ color: ink }}>
                  “{dialog.title}” and every message in it will be removed for everyone with the link.
                </p>
                <p
                  className="mt-3 text-sm leading-relaxed px-3 py-3"
                  style={{ color: ink, backgroundColor: primary + "0D", borderLeft: "3px solid " + primary, borderRadius: "0 " + r + " " + r + " 0" }}
                >
                  There's no undo, and no record of who deleted it. Documents in the library are untouched.
                </p>
                <div className="mt-6 flex justify-end gap-2">
                  <Button
                    type="button"
                    onClick={closeDialog}
                    className={"px-4 py-2.5 text-sm font-semibold " + focusRing}
                    style={{ backgroundColor: "transparent", color: ink, border: "1px solid " + line, borderRadius: r }}
                  >
                    Keep conversation
                  </Button>
                  <Button
                    type="button"
                    data-confirm="true"
                    onClick={confirmDelete}
                    className={"inline-flex items-center gap-2 px-4 py-2.5 text-sm font-bold " + focusRing}
                    style={{ backgroundColor: primary, color: "#FFFFFF", borderRadius: r }}
                  >
                    <Trash className="w-4 h-4" aria-hidden="true" />
                    Delete for everyone
                  </Button>
                </div>
              </div>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}
