"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

type IconName = "grid" | "coin" | "graph" | "gear";

function Icon({ name }: { name: IconName }) {
  const stroke = "currentColor";
  const sw = 1.5;
  switch (name) {
    case "grid":
      return (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={stroke} strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round">
          <rect x="3" y="3" width="7" height="7" rx="1.5" />
          <rect x="14" y="3" width="7" height="7" rx="1.5" />
          <rect x="3" y="14" width="7" height="7" rx="1.5" />
          <rect x="14" y="14" width="7" height="7" rx="1.5" />
        </svg>
      );
    case "coin":
      return (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={stroke} strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round">
          <ellipse cx="12" cy="6" rx="8" ry="3" />
          <path d="M4 6v6c0 1.657 3.582 3 8 3s8-1.343 8-3V6" />
          <path d="M4 12v6c0 1.657 3.582 3 8 3s8-1.343 8-3v-6" />
        </svg>
      );
    case "graph":
      return (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={stroke} strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round">
          <circle cx="5" cy="6" r="2.2" />
          <circle cx="19" cy="6" r="2.2" />
          <circle cx="12" cy="18" r="2.2" />
          <path d="M7 7.5 10.5 16.5M17 7.5 13.5 16.5M7.2 6h9.6" />
        </svg>
      );
    case "gear":
      return (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={stroke} strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="3" />
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
        </svg>
      );
  }
}

const items: { href: string; label: string; icon: IconName }[] = [
  { href: "/",         label: "Dashboard", icon: "grid" },
  { href: "/money",    label: "Money",     icon: "coin" },
  { href: "/graph",    label: "Nexus",     icon: "graph" },
  { href: "/settings", label: "Settings",  icon: "gear" },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <span className="sidebar-logo-mark" aria-hidden>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <path d="M4 12 L10 18 L20 6" />
          </svg>
        </span>
        Chaufferone
      </div>
      <nav className="sidebar-nav">
        {items.map((it) => {
          const active = pathname === it.href || (it.href !== "/" && pathname?.startsWith(it.href));
          return (
            <Link key={it.href} href={it.href} className={`sidebar-link ${active ? "active" : ""}`}>
              <span className="icon"><Icon name={it.icon} /></span>
              {it.label}
            </Link>
          );
        })}
      </nav>
      <div className="sidebar-foot">
        <span className="dot" />
        <span>ORACLE online · v0.1</span>
      </div>
    </aside>
  );
}

export function Topbar() {
  return (
    <header className="topbar">
      <div className="topbar-left">
        <span className="topbar-tag"><span className="dot" /> Live · ORACLE feed</span>
        <span className="ticker" aria-hidden>
          <span className="ticker-track">
            <span className="ticker-item">Next obligation <strong>· due in 3d</strong></span>
            <span className="ticker-item">Cushion <strong>· ₹10,000</strong></span>
            <span className="ticker-item">Floor <strong>· ₹5,000</strong></span>
            <span className="ticker-item">Horizon <strong>· 45 days</strong></span>
            <span className="ticker-item">Next obligation <strong>· due in 3d</strong></span>
            <span className="ticker-item">Cushion <strong>· ₹10,000</strong></span>
            <span className="ticker-item">Floor <strong>· ₹5,000</strong></span>
            <span className="ticker-item">Horizon <strong>· 45 days</strong></span>
          </span>
        </span>
      </div>
      <div className="topbar-right">
        <button className="btn-icon" aria-label="Notifications" title="Notifications">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
            <path d="M6 8a6 6 0 1 1 12 0c0 7 3 9 3 9H3s3-2 3-9" />
            <path d="M10 21a2 2 0 0 0 4 0" />
          </svg>
        </button>
        <button className="btn-icon" aria-label="Toggle theme" title="Theme">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
          </svg>
        </button>
        <button className="btn-primary">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="6" width="18" height="12" rx="2" />
            <path d="M3 10h18" />
          </svg>
          Connect Wallet
        </button>
      </div>
    </header>
  );
}

export function FooterBar() {
  return (
    <div className="footer-bar">
      <div>© {new Date().getFullYear()} Chaufferone · All rights reserved</div>
      <div className="checks">
        <span className="check">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12l4 4L19 6" /></svg>
          KYC Verified
        </span>
        <span className="check">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12l4 4L19 6" /></svg>
          ORACLE Certified
        </span>
      </div>
    </div>
  );
}
