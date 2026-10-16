import { useEffect, useState } from "react";
import { Link, Navigate, useLocation } from "react-router-dom";

import { Icons } from "@/lib/icons";
import Chat from "@/screens/Chat";
import Documents from "@/screens/Documents";
import Setup from "@/screens/Setup";

const NAV_ITEMS: Array<{ to: string; label: string }> = [
  { to: "/chat", label: "Chat" },
  { to: "/documents", label: "Documents" },
  { to: "/setup", label: "Setup & status" },
];

const KNOWN_PATHS = new Set(NAV_ITEMS.map((item) => item.to));

function navLinkClass(active: boolean): string {
  return [
    "block rounded-[var(--brand-radius)] px-3 py-2 text-sm font-medium transition-colors",
    active ? "bg-[var(--brand-hover)] text-[var(--brand-fg)]" : "text-[var(--brand-fg-muted)]",
  ].join(" ");
}

export default function App() {
  const location = useLocation();
  const path = location.pathname;
  const [navOpen, setNavOpen] = useState(false);

  // Each screen, once reached, stays mounted (just hidden) for the rest of the
  // session. That is what keeps an open chat thread's in-memory state intact
  // across a trip to Documents and back (AC-058) -- the component is never
  // torn down, so there is nothing for a round trip to reset.
  const [visited, setVisited] = useState<Set<string>>(() => new Set([path]));
  useEffect(() => {
    setVisited((prev) => (prev.has(path) ? prev : new Set(prev).add(path)));
  }, [path]);

  const closeNav = () => setNavOpen(false);

  const navLinks = (
    <nav className="flex flex-col gap-1" aria-label="Main navigation">
      {NAV_ITEMS.map((item) => (
        <Link
          key={item.to}
          to={item.to}
          onClick={closeNav}
          aria-current={path === item.to ? "page" : undefined}
          className={navLinkClass(path === item.to)}
        >
          {item.label}
        </Link>
      ))}
    </nav>
  );

  const brandTitle = '"chat documents" web app (RAG';

  return (
    <div className="flex min-h-screen w-full flex-col overflow-x-hidden lg:flex-row">
      {/* Mobile/tablet top bar: the only way to reach the other areas below the lg breakpoint. */}
      <div
        className="flex items-center justify-between border-b p-3 lg:hidden"
        style={{ backgroundColor: "var(--brand-surface)", borderColor: "var(--brand-border)" }}
      >
        <p
          className="truncate text-sm font-semibold"
          style={{ fontFamily: "var(--brand-font-heading)" }}
        >
          {brandTitle}
        </p>
        <button
          type="button"
          aria-label={navOpen ? "Close navigation menu" : "Open navigation menu"}
          aria-expanded={navOpen}
          aria-controls="app-nav-drawer"
          onClick={() => setNavOpen((open) => !open)}
          className="shrink-0 rounded-[var(--brand-radius)] p-2"
          style={{ color: "var(--brand-fg-muted)" }}
        >
          {navOpen ? <Icons.X size={20} /> : <Icons.Menu size={20} />}
        </button>
      </div>

      {/* Mobile nav drawer */}
      {navOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div
            className="absolute inset-0 bg-black/40"
            onClick={closeNav}
            aria-hidden="true"
            data-testid="nav-drawer-scrim"
          />
          <aside
            id="app-nav-drawer"
            className="absolute inset-y-0 left-0 w-64 max-w-[80vw] overflow-y-auto border-r p-4"
            style={{ backgroundColor: "var(--brand-surface)", borderColor: "var(--brand-border)" }}
          >
            {navLinks}
          </aside>
        </div>
      )}

      {/* Desktop sidebar: chat, documents and setup all reachable, alongside whichever is open. */}
      <aside
        className="hidden w-56 shrink-0 border-r p-4 lg:block"
        style={{ backgroundColor: "var(--brand-surface)", borderColor: "var(--brand-border)" }}
      >
        <p
          className="mb-4 px-3 text-sm font-semibold"
          style={{ fontFamily: "var(--brand-font-heading)" }}
        >
          {brandTitle}
        </p>
        {navLinks}
      </aside>

      <main className="min-w-0 flex-1 overflow-x-hidden overflow-y-auto">
        {visited.has("/chat") && (
          <div data-testid="chat-panel" hidden={path !== "/chat"}>
            <Chat />
          </div>
        )}
        {visited.has("/documents") && (
          <div data-testid="documents-panel" hidden={path !== "/documents"}>
            <Documents />
          </div>
        )}
        {visited.has("/setup") && (
          <div data-testid="setup-panel" hidden={path !== "/setup"}>
            <Setup />
          </div>
        )}
        {!KNOWN_PATHS.has(path) && <Navigate to="/chat" replace />}
      </main>
    </div>
  );
}
