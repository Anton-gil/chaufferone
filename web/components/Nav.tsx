"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { signOut, useSession } from "next-auth/react";

type Item = { href: string; label: string; icon: React.ReactNode; count?: number };

const primary: Item[] = [
  { href: "/dashboard",     label: "Timeline",      icon: <IconTimeline /> },
  { href: "/subscriptions", label: "Subscriptions", icon: <IconRepeat /> },
  { href: "/money",         label: "Money",         icon: <IconMoney /> },
  { href: "/graph",         label: "Graph",         icon: <IconGraph /> },
  { href: "/insights",      label: "Insights",      icon: <IconMoney /> },
];
const secondary: Item[] = [
  { href: "/network",   label: "Network",  icon: <IconSettings /> },
  { href: "/settings",  label: "Settings", icon: <IconSettings /> },
];

const crumbs: Record<string, string> = {
  "/dashboard":     "Timeline",
  "/subscriptions": "Subscriptions",
  "/money":         "Money",
  "/graph":         "Graph",
  "/insights":      "Insights",
  "/network":       "Network",
  "/settings":      "Settings",
};

export function Sidebar() {
  const pathname = usePathname();
  const isActive = (href: string) => pathname === href || pathname.startsWith(href + "/");

  return (
    <aside className="sidebar">
      <Link href="/" className="sidebar-logo">Chaufferone</Link>

      <div className="sidebar-section-label">Workspace</div>
      <nav className="sidebar-nav">
        {primary.map((it) => (
          <Link key={it.href} href={it.href} className={`sidebar-link ${isActive(it.href) ? "active" : ""}`}>
            <span className="side-icon">{it.icon}</span>
            {it.label}
          </Link>
        ))}
      </nav>

      <div className="sidebar-section-label">Account</div>
      <nav className="sidebar-nav">
        {secondary.map((it) => (
          <Link key={it.href} href={it.href} className={`sidebar-link ${isActive(it.href) ? "active" : ""}`}>
            <span className="side-icon">{it.icon}</span>
            {it.label}
          </Link>
        ))}
      </nav>

      <div className="sidebar-status">
        <div className="sidebar-status-row">
          <span className="sidebar-status-dot" />
          Engine · Live
        </div>
        <div className="sidebar-status-note">Local · v0.1</div>
      </div>
    </aside>
  );
}

export function Topbar() {
  const pathname = usePathname();
  const crumb = crumbs[pathname] ?? (pathname.startsWith("/obligation") ? "Obligation" : "Chaufferone");
  const { data: session, status } = useSession();
  const user = session?.user;
  const initial = (user?.name || user?.email || "?").trim().charAt(0).toUpperCase();
  return (
    <div className="topbar">
      <div className="topbar-left">
        <span className="topbar-crumb">Chaufferone</span>
        <span className="topbar-crumb-sep">/</span>
        <span className="topbar-crumb" style={{ color: "var(--mute-strong)" }}>{crumb}</span>
      </div>
      <div className="topbar-right">
        <div className="topbar-search" role="search">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="7" />
            <line x1="20" y1="20" x2="16.65" y2="16.65" />
          </svg>
          Search obligations…
          <span className="topbar-kbd">⌘K</span>
        </div>
        <Link href="/" className="btn-icon" aria-label="Landing" title="Back to landing">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <path d="M3 12l9-9 9 9" />
            <path d="M5 10v10h14V10" />
          </svg>
        </Link>
        {status === "authenticated" && user ? (
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span style={{ fontSize: 13, color: "var(--mute-strong)", maxWidth: 160, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {user.name ?? user.email}
            </span>
            {user.image ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={user.image}
                alt={user.name ?? "Account"}
                referrerPolicy="no-referrer"
                className="topbar-avatar"
                style={{ padding: 0, objectFit: "cover" }}
                width={32}
                height={32}
              />
            ) : (
              <div className="topbar-avatar" aria-label="Account">{initial}</div>
            )}
            <button
              type="button"
              onClick={() => void signOut({ callbackUrl: "/" })}
              className="btn-icon"
              aria-label="Sign out"
              title="Sign out"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                <polyline points="16 17 21 12 16 7" />
                <line x1="21" y1="12" x2="9" y2="12" />
              </svg>
            </button>
          </div>
        ) : (
          <Link href="/login" className="btn-primary" style={{ padding: "6px 12px", fontSize: 13 }}>
            Sign in
          </Link>
        )}
      </div>
    </div>
  );
}

function IconTimeline() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <line x1="4" y1="6" x2="20" y2="6" />
      <line x1="4" y1="12" x2="14" y2="12" />
      <line x1="4" y1="18" x2="18" y2="18" />
      <circle cx="16" cy="12" r="2" fill="currentColor" />
    </svg>
  );
}
function IconRepeat() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="17 1 21 5 17 9" />
      <path d="M3 11V9a4 4 0 0 1 4-4h14" />
      <polyline points="7 23 3 19 7 15" />
      <path d="M21 13v2a4 4 0 0 1-4 4H3" />
    </svg>
  );
}
function IconMoney() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="3,17 8,12 12,14 17,8 21,10" />
      <line x1="3" y1="20" x2="21" y2="20" strokeDasharray="2 2" />
    </svg>
  );
}
function IconGraph() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="6" cy="6" r="2" />
      <circle cx="18" cy="7" r="2" />
      <circle cx="12" cy="17" r="2.2" fill="currentColor" />
      <line x1="7.5" y1="7" x2="10.5" y2="15" />
      <line x1="16.5" y1="8.5" x2="13.5" y2="15.5" />
    </svg>
  );
}
function IconSettings() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06A1.65 1.65 0 0 0 15 19.4a1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.6 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9 1.65 1.65 0 0 0 4.27 7.18l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.6a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09A1.65 1.65 0 0 0 15 4.6a1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9c.14.31.22.65.23 1v.09" />
    </svg>
  );
}
